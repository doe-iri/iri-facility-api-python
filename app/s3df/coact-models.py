import os
import dataclasses
from typing import List, Optional, Dict, Union, Annotated
import strawberry
from strawberry.types import Info
from strawberry.arguments import UNSET
from typing import NewType
from enum import Enum, IntEnum
import re
import json

from datetime import datetime, date, timedelta
import pytz
from bson import ObjectId

import logging

LOG = logging.getLogger(__name__)

# the database name for all data
DB_NAME = "iris"

MongoId = strawberry.scalar(
    NewType("MongoId", object),
    serialize = lambda v: str(v),
    parse_value = lambda v: ObjectId(v),
)

CoactDatetime = strawberry.scalar(
    NewType("CoactDatetime", object),
    serialize = lambda v: v.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'), # Use var d = new Date(str) in JS to deserialize in Javascript
    parse_value = lambda v: datetime.strptime(v, '%Y-%m-%dT%H:%M:%S.%fZ').astimezone(pytz.utc),
)

Int64 = strawberry.scalar(
    Union[int, str],  # type: ignore
    serialize=lambda v: int(v),
    parse_value=lambda v: str(v),
    description="Int64 field",
)

@strawberry.type
class NameDesc:
    name: Optional[str] = UNSET
    description: Optional[str] = UNSET

# would this be useful? https://github.com/strawberry-graphql/strawberry/discussions/444

# we generally just set everything to be option so that we can create a form like experience with graphql. we impose some of the required fields in some utility functions like create_thing(). not a great use of the graphql spec, but allows to to limit the amount of code we have to write

@strawberry.enum
class CoactRequestType(Enum):
    UserAccount = "UserAccount"
    NewRepo = "NewRepo"
    RenameRepo = "RenameRepo"
    NewFacility = "NewFacility"
    RepoMembership = "RepoMembership"
    RepoRemoveUser = "RepoRemoveUser"
    RepoUpdateFeature = "RepoUpdateFeature"
    UserStorageAllocation = "UserStorageAllocation"
    RepoComputeAllocation = "RepoComputeAllocation"
    RepoStorageAllocation = "RepoStorageAllocation"
    FacilityComputeAllocation = "FacilityComputeAllocation"
    FacilityStorageAllocation = "FacilityStorageAllocation"
    RepoChangeComputeRequirement = "RepoChangeComputeRequirement"
    UserChangeShell = "UserChangeShell"
    UserPublicHtml = "UserPublicHtml"

@strawberry.enum
class CoactRequestStatus(IntEnum):
    NotActedOn = 0
    Approved = 1
    Rejected = -1
    Incomplete = 2
    Completed = 3
    PreApproved = 4

@strawberry.enum
class ComputeRequirement(str, Enum):
    OnShift = "OnShift"
    OffShift = "OffShift"
    Normal = "Normal"

@strawberry.input
class CoactRequestInput:
    reqtype: Optional[CoactRequestType] = UNSET
    requestedby: Optional[str] = UNSET
    timeofrequest: Optional[datetime] = UNSET
    eppn: Optional[str] = UNSET
    username: Optional[str] = UNSET
    preferredUserName: Optional[str] = UNSET
    reponame: Optional[str] = UNSET
    facilityname: Optional[str] = UNSET
    principal: Optional[str] = UNSET
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    clustername: Optional[str] = UNSET
    chargefactor: Optional[float] = 1.0
    storagename: Optional[str] = UNSET
    computerequirement: Optional[ComputeRequirement] = ComputeRequirement.Normal
    purpose: Optional[str] = UNSET
    rootfolder: Optional[str] = UNSET
    allocationid: Optional[MongoId] = UNSET
    percent_of_facility: Optional[float] = 0
    burst_percent_of_facility: Optional[float] = 0
    allocated: Optional[float] = 0 # Absolute compute allocation; similar to facility
    burst_allocated: Optional[float] = 0 # Absolute compute allocation; similar to facility
    gigabytes: Optional[float] = 0
    inodes: Optional[float] = 0
    shell: Optional[str] = UNSET
    previousName: Optional[str] = UNSET
    publichtml: bool = False
    notes: Optional[str] = UNSET
    dontsendemail: Optional[bool] = False # Tells the ansible scripts that this request is being created by automation and will be approved immediately. No need to notify czars that a request is pending.
    approvalstatus: Optional[CoactRequestStatus] = CoactRequestStatus.NotActedOn

@strawberry.type
class CoactRequestAudit:
    actedby: Optional[str] = UNSET
    actedat: Optional[datetime] = None
    notes: Optional[str] = UNSET
    previous: Optional[CoactRequestStatus] = CoactRequestStatus.NotActedOn

@strawberry.type
class CoactRequest(CoactRequestInput):
    _id: Optional[MongoId] = UNSET
    audit: Optional[List[CoactRequestAudit]] = UNSET

    def __init__(self, **kwargs):
        self._id = kwargs.get("_id", None)
        self.audit = [ CoactRequestAudit(**x) for x in kwargs.get("audit", []) ]
        super(CoactRequest, self).__init__(**{ k : v for k,v in kwargs.items() if k not in [ "_id", "audit"]})

    def approve(self, info):
        info.context.db.collection("requests").update_one({"_id": self._id}, {"$set": { "approvalstatus": CoactRequestStatus.Approved.value }, "$push": {"audit": { "previous": self.approvalstatus, "actedby": info.context.username, "actedat": datetime.utcnow()}} })
        return info.context.db.find_request( { "_id": ObjectId(self._id) } )
    def reject(self, notes, info):
        curreq = info.context.db.collection("requests").find_one({"_id": self._id})
        notes = curreq.get("notes", "") + "\n" + notes
        info.context.db.collection("requests").update_one({"_id": self._id}, {"$set": { "approvalstatus": CoactRequestStatus.Rejected.value }, "$push": {"audit": { "previous": self.approvalstatus, "actedby": info.context.username, "actedat": datetime.utcnow(), "notes": notes }}})
        return info.context.db.find_request( { "_id": ObjectId(self._id) } )
    def complete(self, notes, info):
        curreq = info.context.db.collection("requests").find_one({"_id": self._id})
        notes = curreq.get("notes", "") + "\n" + notes
        info.context.db.collection("requests").update_one({"_id": self._id}, {"$set": { "approvalstatus": CoactRequestStatus.Completed.value }, "$push": {"audit": { "previous": self.approvalstatus, "actedby": info.context.username, "actedat": datetime.utcnow(), "notes": notes }}})
        return info.context.db.find_request( { "_id": ObjectId(self._id) } )
    def incomplete(self, notes, info):
        curreq = info.context.db.collection("requests").find_one({"_id": self._id})
        notes = curreq.get("notes", "") + "\n" + notes
        info.context.db.collection("requests").update_one({"_id": self._id}, {"$set": { "approvalstatus": CoactRequestStatus.Incomplete.value }, "$push": {"audit": { "previous": self.approvalstatus, "actedby": info.context.username, "actedat": datetime.utcnow(), "notes": notes }}})
        return info.context.db.find_request( { "_id": ObjectId(self._id) } )
    def refire(self, info) -> bool:
        curreq = info.context.db.collection("requests").find_one({"_id": self._id})
        v = {
          'actedby': info.context.username,
          'actedat': datetime.utcnow(),
          "previous": self.approvalstatus
        }
        return info.context.db.collection("requests").update_one({"_id": self._id}, {"$set": { "approvalstatus": CoactRequestStatus.Approved.value }, "$push": {"audit": v}})
    def reopen(self, info) -> bool:
        curreq = info.context.db.collection("requests").find_one({"_id": self._id})
        v = {
          'actedby': info.context.username,
          'actedat': datetime.utcnow(),
          "previous": self.approvalstatus
        }
        return info.context.db.collection("requests").update_one({"_id": self._id}, {"$set": { "approvalstatus": CoactRequestStatus.NotActedOn }, "$push": {"audit": v}})
    def changeFacility(self, info, newfacilty) -> bool:
        curreq = info.context.db.collection("requests").find_one({"_id": self._id})
        v = {
          'actedby': info.context.username,
          'actedat': datetime.utcnow(),
          "previous": self.approvalstatus,
          "notes": "Changed facility from " + curreq["facilityname"] + " to " + newfacilty
        }
        return info.context.db.collection("requests").update_one({"_id": self._id}, {"$set": { "facilityname": newfacilty }, "$push": {"audit": v}})


@strawberry.type
class CoactRequestWithPerms(CoactRequest):
    canapprove: Optional[bool] = False # Transient property used to indicate if the current user is a leader in the repo. This should NOT be stored in the database
    canrefire: Optional[bool] = False # Transient property used to indicate if the current user has permission to approve. This should NOT be stored in the database

    def __init__(self, **kwargs):
        super(CoactRequestWithPerms, self).__init__(**kwargs)

@strawberry.type
class CoactRequestEvent:
    operationType: str
    theRequest: Optional[CoactRequest] = UNSET

@strawberry.input
class CoactRequestFilter:
    reqtype: Optional[CoactRequestType] = UNSET
    approvalstatus: Optional[CoactRequestStatus] = UNSET
    reponame: Optional[str] = UNSET
    facilityname: Optional[str] = UNSET
    windowbegin: Optional[datetime] = UNSET
    windowend: Optional[datetime] = UNSET
    foruser: Optional[str] = UNSET

@strawberry.input
class EppnInput:
    eppn: Optional[str] = UNSET
    fullname: Optional[str] = UNSET
    email: Optional[str] = UNSET
    organization: Optional[str] = UNSET

@strawberry.type
class Eppn(EppnInput):
    pass

@strawberry.type
class UserStorageUsage:
    _id: Optional[MongoId] = UNSET
    gigabytes: Optional[float] = 0
    inodes: Optional[float] = 0
    date: Optional[datetime] = UNSET
    allocid: Optional[float] = 0

@strawberry.input
class UserStorageInput:
    _id: Optional[MongoId] = UNSET
    username: Optional[str] = UNSET
    purpose: Optional[str] = UNSET
    gigabytes: Optional[float] = 0
    inodes: Optional[float] = 0
    storagename: Optional[str] = UNSET
    rootfolder: Optional[str] = UNSET
    def validate(self, fields=["storagename", "purpose", "gigabytes", "rootfolder"]):
        for f in fields:
            if not getattr(self,f):
                raise Exception(f"Attribute {f} is required")
    

@strawberry.type
class UserStorage(UserStorageInput):
    usage: Optional[UserStorageUsage]

@strawberry.type
class UserRegistration(EppnInput):
    isRegistered: Optional[bool] = UNSET
    isRegistrationPending: Optional[bool] = UNSET
    fullname: Optional[str] = UNSET
    requestId: Optional[MongoId] = UNSET
    username: Optional[str] = UNSET
    @strawberry.field
    def requestObj(self, info) -> Optional[CoactRequest]:
        if not self.requestId:
            return CoactRequest()
        return info.context.db.find_request({"_id": self.requestId})

@strawberry.input
class UserInput:
    _id: Optional[MongoId] = UNSET
    username: Optional[str] = UNSET
    fullname: Optional[str] = UNSET
    uidnumber: Optional[int] = None
    eppns: Optional[List[str]] = UNSET
    preferredemail: Optional[str] = UNSET
    shell: Optional[str] = UNSET
    publichtml: bool = False
    isbot: bool = False

@strawberry.type
class User(UserInput):
    # eppnObjs is most likely a call to some external service to get the details of an eppn
    # For now we assume everyone is a SLAC person.
    @strawberry.field
    def eppnObjs(self, info) -> List[Eppn]:
        ret = [ ]
        if self.eppns is UNSET:
            return []
        for x in self.eppns:
            if '@' not in x:
                ret.append(Eppn(**{ "eppn": x+"@slac.stanford.edu", "fullname": x, "email": x+"@slac.stanford.edu", "organization": "slac.stanford.edu" }))
            else:
                ret.append(Eppn(**{ "eppn": x, "fullname": x.split("@")[0], "email": x, "organization": x.split("@")[1] }))
        return ret
    @strawberry.field
    def facilities(self, info) -> List[str]:
        return sorted(list(set([x["facility"] for x in info.context.db.collection("repos").find({"name": "default", "users": self.username}, {"_id": 0, "facility": 1})])))
    @strawberry.field
    def isAdmin(self, info) -> bool:
        admins = re.sub( "\s", "", os.environ.get("ADMIN_USERNAMES",'')).split(',')
        return self.username in admins
    @strawberry.field
    def isCzar(self, info) -> bool:
        myfacs = list(info.context.db.collection("facilities").find({"czars": self.username}, {"_id": 0, "name": 1}))
        if myfacs:
            return True
        return False
    @strawberry.field
    def subjectFacilities(self, info) -> List[str]:
        """ Facilities for which I am a czar """
        return [ x["name"] for x in info.context.db.collection("facilities").find({"czars": self.username}, {"_id": 0, "name": 1})]
    @strawberry.field
    def isImpersonating(self, info) -> bool:
        return info.context.is_impersonating
    @strawberry.field
    def groups(self, info) -> List[str]:
        grps = info.context.db.collection("access_groups").find({"members": self.username})
        if not grps:
            return []
        return [ x["name"] for x in grps]
    @strawberry.field
    def storages(self, info) -> List[UserStorage]:
        storages = list(info.context.db.collection("user_storage_allocation").find({"username": self.username}))
        if not storages:
            return []
        for storage in storages:
            usages = list(info.context.db.collection("user_storage_usage").find({"allocid": storage["_id"]}).sort([("date", -1)]).limit(1))
            if usages:
                storage["usage"] = UserStorageUsage(**usages[0])
            else:
                storage["usage"] = UserStorageUsage(**{"_id": None, "allocid": storage["_id"], "gigabytes": 0, "inodes": 0, "date": datetime.utcnow() })
        print(storages)
        return [ UserStorage(**storage) for storage in storages ]
    @strawberry.field
    def earliestCompletedUserAccountRegistration(self, info) -> Optional[datetime]:
        req = list(info.context.db.collection("requests").find({"preferredUserName": info.context.username, "reqtype": "UserAccount", "approvalstatus": { "$in": [ 1, 3 ]}}).sort([("timeofrequest", 1)]).limit(1))
        return req[0].get("timeofrequest", None) if req else None

@strawberry.type
class RepoFacilityName:
    name: str
    facility: str

@strawberry.input
class ClusterInput:
    _id: Optional[MongoId] = UNSET
    name: Optional[str] = UNSET
    nodecpucount: Optional[int] = UNSET
    nodecpucountdivisor: Optional[int] = UNSET
    nodegpucount: Optional[int] = UNSET
    nodememgb: Optional[int] = UNSET
    nodegpumemgb: Optional[int] = UNSET
    chargefactor: Optional[float] = UNSET
    nodecpusmt: Optional[int] = UNSET
    members: Optional[List[str]] = UNSET
    memberprefixes: Optional[List[str]] = UNSET

@strawberry.type
class Cluster(ClusterInput):
    pass

@strawberry.type
class ClusterTotals:
    clustername: str
    totalpurchased: int

@strawberry.input
class ComputeAllocationInput:
    _id: Optional[MongoId] = UNSET
    start: Optional[datetime] = UNSET
    end: Optional[datetime] = UNSET
    clustername: Optional[str] = UNSET
    servers: Optional[float] = UNSET

@strawberry.input
class StorageAllocationInput:
    _id: Optional[MongoId] = UNSET
    start: Optional[datetime] = UNSET
    end: Optional[datetime] = UNSET
    storagename: Optional[str] = UNSET
    gigabytes: Optional[float] = UNSET
    inodes: Optional[float] = UNSET

@strawberry.type
class FacilityComputeAllocation(ComputeAllocationInput):
    pass

@strawberry.type
class FacilityStorageAllocation(StorageAllocationInput):
    pass

# Types for the FAcilities list view page.
@strawberry.type
class FacilityComputePurchases:
    clustername: Optional[str] = UNSET
    purchased: Optional[float] = UNSET
    burst_percent: Optional[float] = UNSET
    allocated: Optional[float] = UNSET
@strawberry.type
class FacilityStoragePurchases:
    storagename: Optional[str] = UNSET
    purpose: Optional[str] = UNSET
    purchased: Optional[float] = UNSET
    allocated: Optional[float] = UNSET
    used: Optional[float] = UNSET

@strawberry.input
class FacilityInput:
    _id: Optional[MongoId] = UNSET
    name: Optional[str] = UNSET
    description: Optional[str] = UNSET
    resources: Optional[List[str]] = UNSET
    serviceaccount: Optional[str] = UNSET
    servicegroup: Optional[str] = UNSET
    czars: Optional[List[str]] = UNSET

@strawberry.type
class Facility( FacilityInput ):
    @strawberry.field
    def czarObjs(self, info) -> List[User]:
        ret = []
        for cz in self.czars:
            ret.append(info.context.db.find_user({"username": cz}))
        return ret
    @strawberry.field
    def computepurchases(self, info) -> Optional[List[FacilityComputePurchases]]:
        # More complex; we want to return the "current" per resource type.
        todaysdate = datetime.utcnow()
        aggs = info.context.db.collection("facility_compute_purchases").aggregate([
            { "$match": { "facility": self.name, "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }},
            { "$sort": { "end": -1 }},
            { "$group": { "_id": {"clustername": "$clustername"}, "servers": {"$sum": "$servers"}, "burst_percent": {"$max": "$burst_percent"}}},
        ])
        purchases = { x["_id"]["clustername"]: { "purchased": x["servers"], "burst_percent": x.get("burst_percent", 0) if x["burst_percent"] else 0 } for x in aggs }
        aaggs = info.context.db.collection("repos").aggregate([
            { "$match": { "facility": self.name}},
            { "$lookup": { "from": "repo_compute_allocations", "localField": "_id", "foreignField": "repoid", "as": "allocation"}},
            { "$unwind": "$allocation" },
            { "$replaceRoot": { "newRoot": "$allocation" } },
            { "$match": { "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }},
            { "$group": { "_id": {"clustername": "$clustername"}, "percent_of_facility": {"$sum": "$percent_of_facility"}}},
            { "$project": { "clustername": "$_id.clustername", "percent_of_facility": "$percent_of_facility" }}
        ])
        allocs = { x["clustername"]: x["percent_of_facility"] for x in aaggs }
        for k,v in purchases.items():
            v["clustername"] = k
            v["allocated"] = allocs.get(k, 0)
        return [ FacilityComputePurchases(**{k:x.get(k, 0) for k in ["clustername", "purchased", "burst_percent", "allocated"] }) for x in purchases.values()]
    @strawberry.field
    def computeallocations(self, info) -> Optional[List[FacilityComputeAllocation]]:
        # More complex; we want to return the "current" per resource type.
        todaysdate = datetime.utcnow()
        current_allocs = info.context.db.collection("repos").aggregate([
            { "$match": { "facility": self.name}},
            { "$lookup": { "from": "repo_compute_allocations", "localField": "_id", "foreignField": "repoid", "as": "allocation"}},
            { "$unwind": "$allocation" },
            { "$replaceRoot": { "newRoot": "$allocation" } },
            { "$match": { "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }},
            { "$group": { "_id": {"clustername": "$clustername"}, "servers": {"$sum": "$servers"}}},
        ])
        return [ FacilityComputeAllocation(**{k:x.get(k, 0) for k in ["_id", "clustername", "servers" ] }) for x in current_allocs]
    @strawberry.field
    def storagepurchases(self, info) -> Optional[List[FacilityStoragePurchases]]:
        # More complex; we want to return the "current" per resource type.
        todaysdate = datetime.utcnow()
        aggs = info.context.db.collection("facility_storage_purchases").aggregate([
            { "$match": { "facility": self.name, "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }},
            { "$sort": { "end": -1 }},
            { "$group": { "_id": {"storagename": "$storagename", "purpose": "$purpose"}, "gigabytes": {"$sum": "$gigabytes"}}},
        ])
        purchases = { (x["_id"]["storagename"], x["_id"]["purpose"]): { "purchased": x["gigabytes"] } for x in aggs }
        LOG.error("Purchases for %s is %s", self.name, purchases)
        aaggs = info.context.db.collection("repos").aggregate([
            { "$match": { "facility": self.name}},
            { "$lookup": { "from": "repo_storage_allocations", "localField": "_id", "foreignField": "repoid", "as": "allocation"}},
            { "$unwind": "$allocation" },
            { "$replaceRoot": { "newRoot": "$allocation" } },
            { "$match": { "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }},
            { "$group": { "_id": {"storagename": "$storagename", "purpose": "$purpose"}, "gigabytes": {"$sum": "$gigabytes"}}},
        ])
        allocs = { (x["_id"]["storagename"], x["_id"]["purpose"]): x["gigabytes"] for x in aaggs }
        LOG.error("Allocations for %s is %s", self.name, allocs)
        uaggs = info.context.db.collection("repos").aggregate([
            { "$match": { "facility": self.name}},
            { "$lookup": { "from": "repo_storage_allocations", "localField": "_id", "foreignField": "repoid", "as": "allocation"}},
            { "$unwind": "$allocation" },
            { "$replaceRoot": { "newRoot": "$allocation" } },
            { "$match": { "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }},
            { "$lookup": { "from": "repo_overall_storage_usage", "localField": "_id", "foreignField": "allocationid", "as": "usage"}},
            { "$unwind": "$usage" },
            { "$group": { "_id": {"storagename": "$storagename", "purpose": "$purpose"}, "gigabytes": {"$sum": "$usage.gigabytes"}}},
        ])
        used = { (x["_id"]["storagename"], x["_id"]["purpose"]): x["gigabytes"] for x in uaggs }
        LOG.error("Used for %s is %s", self.name, used)
        for k,v in purchases.items():
            v["storagename"] = k[0]
            v["purpose"] = k[1]
            v["allocated"] = allocs.get(k, 0)
            v["used"] = used.get(k, 0)
        return [ FacilityStoragePurchases(**{k:x.get(k, 0) for k in ["storagename", "purpose", "purchased", "allocated", "used" ] }) for x in purchases.values()]

@strawberry.type
class FacillityPastXUsage:
    facility: Optional[str] = UNSET
    clustername: Optional[str] = UNSET
    resourceHours: Optional[float] = 0
    percentUsed: float

@strawberry.type
class RepoPastXUsage:
    name: Optional[str] = UNSET
    facility: Optional[str] = UNSET
    clustername: Optional[str] = UNSET
    resourceHours: Optional[float] = 0
    percentUsed: float

@strawberry.input
class UsageInput:
    facility: Optional[str] = UNSET
    repo: Optional[str] = UNSET
    repoid: Optional[MongoId] = UNSET
    qos: Optional[str] = UNSET
    clustername: Optional[str] = UNSET
    storagename: Optional[str] = UNSET
    purpose: Optional[str] = UNSET
    resourceHours: Optional[float] = 0
    gigabytes: Optional[float] = 0
    inodes: Optional[float] = 0

@strawberry.type
class Usage(UsageInput):
    pass

@strawberry.type
class PerDateUsage(Usage):
    date: Optional[datetime] = UNSET

@strawberry.type
class ComputeUsageOverTime:
    start: Optional[datetime] = UNSET
    end: Optional[datetime] = UNSET
    allocatedResourceHours: float
    usedResourceHours: float
    percentUsed: float

@strawberry.type
class FacilityClusterUsage:
    clustername: Optional[str] = UNSET
    purchased: Optional[float] = 0
    nodecpucount: Optional[float] = 0
    availableResourceHours: Optional[float] = 0
    usedResourceHours: float
    percentUsed: float

@strawberry.type
class PerUserUsage(Usage):
    username: Optional[str] = UNSET

@strawberry.type
class PerFolderUsage(Usage):
    folder: Optional[str] = UNSET

@strawberry.input
class ReportRangeInput:
    start: Optional[datetime] = UNSET
    end: Optional[datetime] = UNSET

@strawberry.input
class UserAllocationInput():
    allocationid: Optional[MongoId] = UNSET
    username: Optional[str] = UNSET
    percent: Optional[float] = UNSET

@strawberry.type
class UserAllocation(UserAllocationInput):
    pass


@strawberry.input
class RepoFeatureInput:
  name: str
  state: bool
  options: Optional[List[str]] = UNSET

@strawberry.type
class RepoFeature(RepoFeatureInput):
    pass

@strawberry.input
class RepoComputeAllocationInput:
    _id: Optional[MongoId] = UNSET
    repoid: Optional[MongoId] = UNSET
    clustername: Optional[str] = UNSET
    start: Optional[datetime] = UNSET
    end: Optional[datetime] = UNSET
    percent_of_facility: Optional[float] = UNSET
    burst_percent_of_facility: Optional[float] = 0
    allocated: Optional[float] = 0 # Absolute compute allocation; based on facility purchases and cached here for performance reasons
    burst_allocated: Optional[float] = 0 # Absolute burst allocation; based on facility purchases and cached here for performance reasons

@strawberry.type
class RepoComputeAllocation(RepoComputeAllocationInput):
    @strawberry.field
    def userAllocations(self, info) ->List[UserAllocation]:
        rc_filter = { "allocationid": self._id }
        return [ UserAllocation(**{k:x.get(k, 0) for k in ["username", "percent"] }) for x in  info.context.db.collection("user_allocations").find(rc_filter) ]
    @strawberry.field
    def usage(self, info) ->List[Usage]:
        """
        Overall usage; so pick up from the cached collections.
        """
        LOG.debug("Getting the total usage for repo %s", self.repoid)
        usages = []
        usg = info.context.db.collection("repo_overall_compute_usage").find_one({"allocationId": self._id})
        if usg:
            usages.append({
                "repoid": self.repoid,
                "clustername": self.clustername,
                "resourceHours": usg["resourceHours"]
            })
        return [ Usage(**x) for x in  usages ]
    @strawberry.field
    def perDateUsage(self, info, pastDays: Optional[int] = 0) ->List[PerDateUsage]:
        query = {"allocationId": self._id}
        if pastDays > 0:
            after = datetime.utcnow() - timedelta(days = pastDays)
            query["date"] = { "$gte": after }
        results = info.context.db.collection("repo_daily_compute_usage").find(query)
        return info.context.db.cursor_to_objlist(results, PerDateUsage, exclude_fields={"_id", "allocationId"})

    @strawberry.field
    def perUserUsage(self, info) ->List[PerUserUsage]:
        results = info.context.db.collection("repo_peruser_compute_usage").find({"allocationId": self._id})
        return info.context.db.cursor_to_objlist(results, PerUserUsage, exclude_fields={"_id", "allocationId"})

    # deprecate?
    @strawberry.field
    def clusterNodeCPUCount(self, info) -> int:
        return info.context.db.collection("clusters").find_one({"name": self.clustername})["nodecpucount"]

    @strawberry.field
    def allocatedNodesCount(self, info) -> float:
        return self.allocated

    @strawberry.field
    def allocatedCpusCount(self, info) -> float:
        return round(self.allocated * info.context.db.collection("clusters").find_one({"name": self.clustername})["nodecpucount"])

    @strawberry.field
    def allocatedGpusCount(self, info) -> float:
        return round(self.allocated * info.context.db.collection("clusters").find_one({"name": self.clustername})["nodegpucount"])

    @strawberry.field
    def allocatedMemGb(self, info) -> float:
        return round(self.allocated * info.context.db.collection("clusters").find_one({"name": self.clustername})["nodememgb"])

    @strawberry.field
    def allocatedGpuMemGb(self, info) -> float:
        return round(self.allocated * info.context.db.collection("clusters").find_one({"name": self.clustername})["nodegpumemgb"])


@strawberry.input
class RepoStorageAllocationInput:
    _id: Optional[MongoId] = UNSET
    repoid: Optional[MongoId] = UNSET
    storagename: Optional[str] = UNSET
    purpose: Optional[str] = UNSET
    rootfolder: Optional[str] = UNSET
    start: Optional[datetime] = UNSET
    end: Optional[datetime] = UNSET
    gigabytes: Optional[float] = UNSET
    inodes: Optional[float] = UNSET

@strawberry.type
class RepoStorageAllocation(RepoStorageAllocationInput):
    @strawberry.field
    def usage(self, info) -> Optional[Usage]:
        """
        Overall usage; so pick up from the cached collections.
        """
        LOG.debug("Getting the total storage usage for repo %s", self.repoid)
        usgs = list(info.context.db.collection("repo_overall_storage_usage").find({"allocationid": self._id}).sort([("date", -1)]).limit(1))
        if not usgs:
            return Usage(**{ "repo": self.repoid, "storagename": self.storagename })
        usg = usgs[0]
        return Usage(**{
            "repoid": self.repoid,
            "storagename": self.storagename,
            "gigabytes": usg["gigabytes"],
            "inodes": usg["inodes"]
        })
    @strawberry.field
    def perDateUsage(self, info, year: int) -> List[PerDateUsage]:
        """
        Return all the daily usages for this allocation for the specified year
        """
        jan1thisyear = datetime.now().replace(year=year,month=1, day=1)
        jan1nextyear = jan1thisyear.replace(year=year+1)
        usgs = info.context.db.collection("repo_daily_storage_usage").find({"allocationid": self._id, "date": {"$gte": jan1thisyear, "$lt": jan1nextyear}}, {"_id": 0, "date": 1, "gigabytes": 1, "inodes": 1}).sort([("date", -1)])
        if not usgs:
            return []
        return [ PerDateUsage(**x) for x in  usgs ]

@strawberry.input
class AccessGroupInput:
    _id: Optional[MongoId] = UNSET
    state: Optional[str] = UNSET
    gidnumber: Optional[int] = None # perhaps we should use a linux non-specific name?
    name: Optional[str] = UNSET
    repoid: Optional[MongoId] = UNSET
    members: Optional[List[str]] = UNSET

@strawberry.type
class AccessGroup( AccessGroupInput ):
    @strawberry.field
    def memberObjs(self, info) ->List[User]:
        if self.members is UNSET:
            return []
        return info.context.db.find_users({"username": {"$in": self.members}})

@strawberry.input
class RepoInput:
    _id: Optional[MongoId] = UNSET
    state: Optional[str] = UNSET
    name: Optional[str] = UNSET
    facility: Optional[str] = UNSET

    principal: Optional[str] = UNSET
    leaders: Optional[List[str]] = UNSET
    users: Optional[List[str]] = UNSET

    computerequirement: Optional[ComputeRequirement] = None

    group: Optional[str] = UNSET
    description: Optional[str] = UNSET

@strawberry.type
class Repo( RepoInput ):
    @strawberry.field
    def features(self, info) -> Optional[List[RepoFeature]]:
        repoobj = info.context.db.collection("repos").find_one({"_id": self._id})
        features = repoobj.get("features", {})
        ret = []
        for feature_name, feature in features.items():
            ret.append(RepoFeature(**{"name": feature_name, "state": feature.get("state", True), "options": feature.get("options", None)}))
        return ret

    @strawberry.field
    def facilityObj(self, info) -> Facility:
        return info.context.db.find_facility({"name": self.facility})

    @strawberry.field
    def allUsers(self, info) -> List[User]:
        allusernames = list(set(self.users).union(set(self.leaders).union(set(list(self.principal)))))
        return info.context.db.find_users({"username": {"$in": allusernames}})

    @strawberry.field
    def accessGroupObjs(self, info) ->List[AccessGroup]:
        return info.context.db.find_access_groups({"repoid": self._id})

    @strawberry.field
    def currentComputeAllocations(self, info) ->List[RepoComputeAllocation]:
        """
        Each repo can have multiple allocation objects.
        This call should return an array of "current" allocations; one for each compute resource.
        """
        rc_filter = { "facility": self.facility, "repoid": self._id}
        todaysdate = datetime.utcnow()
        # More complex; we want to return the "current" per resource type.
        current_allocs = info.context.db.collection("repo_compute_allocations").aggregate([
            { "$match": { "repoid": self._id, "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }},
            { "$sort": { "end": -1 }},
            { "$group": { "_id": {"repoid": "$repoid", "clustername": "$clustername"}, "origid": {"$first": "$_id"}}},
        ])
        current_alloc_ids = list(map(lambda x: x["origid"], current_allocs))
        return [ RepoComputeAllocation(**{k:x.get(k, 0) for k in ["_id", "repoid", "clustername", "start", "end", "percent_of_facility", "burst_percent_of_facility", "allocated", "burst_allocated" ] }) for x in  info.context.db.collection("repo_compute_allocations").find({"_id" : {"$in": current_alloc_ids}})]

    @strawberry.field
    def computeAllocation(self, info, allocationid: MongoId) -> Optional[RepoComputeAllocation]:
        """
        Return the specific storage allocation for this repo
        """
        rc_filter = { "_id": allocationid, "repoid": self._id}
        alloc = info.context.db.collection("repo_compute_allocations").find_one(rc_filter)
        if not alloc:
            return None
        return RepoComputeAllocation(**alloc)

    @strawberry.field
    def currentStorageAllocations(self, info) ->List[RepoStorageAllocation]:
        """
        Each repo can have multiple allocation objects.
        This call should return an array of "current" allocations; one for each compute resource.
        """
        rc_filter = { "facility": self.facility, "repoid": self._id}
        todaysdate = datetime.utcnow()
        # More complex; we want to return the "current" per resource type.
        current_allocs = info.context.db.collection("repo_storage_allocations").aggregate([
            { "$match": { "repoid": self._id, "start": {"$lte": todaysdate}, "end": {"$gt": todaysdate} }},
            { "$sort": { "end": -1 }},
            { "$group": { "_id": {"repoid": "$repoid", "purpose": "$purpose"}, "origid": {"$first": "$_id"}}},
        ])
        current_alloc_ids = list(map(lambda x: x["origid"], current_allocs))
        return [ RepoStorageAllocation(**{k:x.get(k, 0) for k in ["_id", "repoid", "storagename", "purpose", "rootfolder", "start", "end", "gigabytes", "inodes" ] }) for x in  info.context.db.collection("repo_storage_allocations").find({"_id" : {"$in": current_alloc_ids}})]

    @strawberry.field
    def storageAllocation(self, info, allocationid: MongoId) -> Optional[RepoStorageAllocation]:
        """
        Return the specific storage allocation for this repo
        """
        rc_filter = { "_id": allocationid, "repoid": self._id}
        alloc = info.context.db.collection("repo_storage_allocations").find_one(rc_filter)
        if not alloc:
            return None
        return RepoStorageAllocation(**alloc)

@strawberry.type
class BulkOpsResult:
    insertedCount: int
    upsertedCount: int
    modifiedCount: int
    deletedCount: int

@strawberry.type
class StatusResult:
    status: bool

@strawberry.input
class Job:
    jobId: Int64
    username: str
    allocationId: MongoId
    qos: str
    startTs: datetime
    endTs: datetime
    resourceHours: float

@strawberry.type
class NormalizedJob(Job):
    durationMillis: Int64
    normalizedResourceHours: float

@strawberry.input
class StorageDailyUsageInput:
    allocationid: Optional[MongoId] = UNSET
    date: Optional[datetime] = UNSET
    gigabytes: Optional[float] = UNSET
    inodes: Optional[float] = UNSET

@strawberry.type
class StorageDailyUsage(StorageDailyUsageInput):
    pass

@strawberry.enum
class AuditTrailObjectType(Enum):
    User = "User"
    Repo = "Repo"
    Facility = "Facility"

@strawberry.input
class AuditTrailInput:
    _id: Optional[MongoId] = UNSET
    type: Optional[AuditTrailObjectType] = UNSET
    actedon: Optional[MongoId] = UNSET # userid in case of user; repoid in case of repo; facilityid in the case of facility
    action: Optional[str] = UNSET
    actedby: Optional[str] = UNSET
    actedat: Optional[datetime] = UNSET
    details: Optional[str] = UNSET

@strawberry.type
class AuditTrail(AuditTrailInput):
    @strawberry.field
    def actedonObj(self, info) -> Optional[Union[User, Repo, Facility]]:
        """
        Return the object that is being acted on.
        """
        if self.type == AuditTrailObjectType.User:
            return info.context.db.find_user({"_id": self.actedon})
        elif self.type == AuditTrailObjectType.Repo:
            return info.context.db.find_repo({"_id": self.actedon})
        if self.type == AuditTrailObjectType.Facility:
            return info.context.db.find_facility({"_id": self.actedon})

@strawberry.input
class NotificationInput:
    to: Optional[List[str]] = UNSET
    cc: Optional[List[str]] = UNSET
    bcc: Optional[List[str]] = UNSET
    subject: Optional[str] = UNSET
    body: Optional[str] = UNSET
    
@strawberry.type
class Notification(NotificationInput):
    pass

