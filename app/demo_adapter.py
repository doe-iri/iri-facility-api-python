from fastapi import Request
import datetime
import random
import uuid
import psij
import time
from .routers.status import models as status_models, facility_adapter as status_adapter
from .routers.account import models as account_models, facility_adapter as account_adapter
from .routers.compute import models as compute_models, facility_adapter as compute_adapter


class DemoAdapter(status_adapter.FacilityAdapter, account_adapter.FacilityAdapter, compute_adapter.FacilityAdapter):
    def __init__(self):
        self.resources = []
        self.incidents = []
        self.events = []
        self.capabilities = {}
        self.user = account_models.User(id="gtorok", name="Gabor Torok")
        self.projects = []
        self.project_allocations = []
        self.user_allocations = []

        self._init_state()

    
    def _init_state(self):

        day_ago = datetime.datetime.now() - datetime.timedelta(days=1)
        self.capabilities = {
            "cpu": account_models.Capability(id=str(uuid.uuid4()), name="CPU Nodes", units=[account_models.AllocationUnit.node_hours]),
            "gpu": account_models.Capability(id=str(uuid.uuid4()), name="GPU Nodes", units=[account_models.AllocationUnit.node_hours]),
            "hpss": account_models.Capability(id=str(uuid.uuid4()), name="Tape Storage", units=[account_models.AllocationUnit.bytes, account_models.AllocationUnit.inodes]),
            "gpfs": account_models.Capability(id=str(uuid.uuid4()), name="GPFS Storage", units=[account_models.AllocationUnit.bytes, account_models.AllocationUnit.inodes]),
        }

        pm = status_models.Resource(id=str(uuid.uuid4()), group="perlmutter", name="compute nodes", description="the perlmutter computer compute nodes", capability_ids=[
            self.capabilities["cpu"].id,
            self.capabilities["gpu"].id,
        ], current_status=status_models.Status.degraded, last_modified=day_ago, resource_type=status_models.ResourceType.compute)
        hpss = status_models.Resource(id=str(uuid.uuid4()), group="hpss", name="hpss", description="hpss tape storage", capability_ids=[self.capabilities["hpss"].id], current_status=status_models.Status.up, last_modified=day_ago, resource_type=status_models.ResourceType.storage)
        cfs = status_models.Resource(id=str(uuid.uuid4()), group="cfs", name="cfs", description="cfs storage", capability_ids=[self.capabilities["gpfs"].id], current_status=status_models.Status.up, last_modified=day_ago, resource_type=status_models.ResourceType.storage)

        self.resources = [
            pm,
            hpss,
            cfs,
            status_models.Resource(id=str(uuid.uuid4()), group="perlmutter", name="login nodes", description="the perlmutter computer login nodes", capability_ids=[], current_status=status_models.Status.degraded, last_modified=day_ago, resource_type=status_models.ResourceType.system),
            status_models.Resource(id=str(uuid.uuid4()), group="services", name="Iris", description="Iris webapp", capability_ids=[], current_status=status_models.Status.down, last_modified=day_ago, resource_type=status_models.ResourceType.website),
            status_models.Resource(id=str(uuid.uuid4()), group="services", name="sfapi", description="the Superfacility API", capability_ids=[], current_status=status_models.Status.up, last_modified=day_ago, resource_type=status_models.ResourceType.service),
        ]

        self.projects = [
            account_models.Project(
                id=str(uuid.uuid4()),
                name="Staff research project",
                description="Compute and storage allocation for staff research use",
                user_ids=[ "gtorok" ],
            ),
            account_models.Project(
                id=str(uuid.uuid4()),
                name="Test project",
                description="Compute and storage allocation for testing use",
                user_ids=[ "gtorok" ],
            ),
        ]

        for p in self.projects:
            for c in self.capabilities.values():
                pa = account_models.ProjectAllocation(
                    id=str(uuid.uuid4()),
                    project_id=p.id,
                    capability_id=c.id,
                    entries=[
                        account_models.AllocationEntry(
                            allocation=500 + random.random() * 500,
                            usage=100 + random.random() * 100,
                            unit=cu,
                        )
                        for cu in c.units
                    ]
                )
                self.project_allocations.append(pa)
                self.user_allocations.append(
                    account_models.UserAllocation(
                        id=str(uuid.uuid4()),
                        project_id=pa.project_id,
                        project_allocation_id=pa.id,
                        user_id="gtorok",
                        entries=[
                            account_models.AllocationEntry(
                                allocation=a.allocation/10,
                                usage=a.usage/10,
                                unit=a.unit
                            ) 
                            for a in pa.entries
                        ]
                    )
                )

        statuses = { r.name: status_models.Status.up for r in self.resources }        
        last_incidents = {}
        d = datetime.datetime(2025, 3, 1, 10, 0, 0)

        # generate some events and incidents
        # here every incident only has events from a single resource, 
        # but in reality it is possible for an incident to have events from multiple resources
        for i in range(0, 1000):
            r = random.choice(self.resources)
            status = statuses[r.name]
            event = status_models.Event(
                id=str(uuid.uuid4()),
                name=f"{r.name} is {status.value}",
                description=f"{r.name} is {status.value}",
                occurred_at=d,
                status=status,
                resource_id=r.id,
                last_modified=day_ago,
            )
            self.events.append(event)
            if r.name in last_incidents:
                inc = last_incidents[r.name]
                event.incident_id = inc.id
                inc.event_ids.append(event.id)
                if status == status_models.Status.up:
                    inc.end = d
                    del last_incidents[r.name]
            
            if random.random() > 0.9:
                if status == status_models.Status.down:
                    statuses[r.name] = status_models.Status.up
                else:
                    statuses[r.name] = status_models.Status.down
                    dstr = d.strftime("%Y-%m-%d %H:%M:%S.%f%z")
                    incident = status_models.Incident(
                        id=str(uuid.uuid4()), 
                        name=f"{r.name} incident at {dstr}", 
                        description=f"{r.name} incident at {dstr}", 
                        status=status_models.Status.down,
                        event_ids=[],
                        resource_ids=random.choices([r.id for r in self.resources], k=3),
                        start=d,
                        end=d,
                        type=random.choice(list(status_models.IncidentType)),
                        resolution="PM was fixed by NERSC staff",
                        last_modified=d
                    )
                    self.incidents.append(incident)
                    last_incidents[r.name] = incident
                    

            d += datetime.timedelta(minutes=int(random.random() * 15 + 1))


    async def get_resources(
        self : "DemoAdapter",
        offset : int,
        limit : int,
        name : str | None = None,
        description : str | None = None,
        group : str | None = None,
        modified_since : datetime.datetime | None = None,
        resource_type : status_models.ResourceType | None = None,
        ) -> list[status_models.Resource]:
        return status_models.Resource.find(self.resources, name, description, group, modified_since, resource_type)[offset:offset + limit]


    async def get_resource(
        self : "DemoAdapter",
        id : str
        ) -> status_models.Resource:
        return status_models.Resource.find_by_id(self.resources, id)


    async def get_events(
        self : "DemoAdapter",
        incident_id : str,
        offset : int,
        limit : int,
        resource_id : str | None = None,
        name : str | None = None,
        description : str | None = None,
        status : status_models.Status | None = None,
        from_ : datetime.datetime | None = None,
        to : datetime.datetime | None = None,
        time_ : datetime.datetime | None = None,
        modified_since : datetime.datetime | None = None,
        ) -> list[status_models.Event]:        
        return status_models.Event.find([e for e in self.events if e.incident_id == incident_id], resource_id, name, description, status, from_, to, time_, modified_since)[offset:offset + limit]


    async def get_event(
        self : "DemoAdapter",
        incident_id : str,
        id : str
        ) -> status_models.Event:
        return status_models.Event.find_by_id(self.events, id)


    async def get_incidents(
        self : "DemoAdapter",
        offset : int,
        limit : int,
        name : str | None = None,
        description : str | None = None,
        status : status_models.Status | None = None,
        type : status_models.IncidentType | None = None,
        from_ : datetime.datetime | None = None,
        to : datetime.datetime | None = None,
        time_ : datetime.datetime | None = None,
        modified_since : datetime.datetime | None = None,
        resource_id : str | None = None,
        ) -> list[status_models.Incident]:
        return status_models.Incident.find(self.incidents, name, description, status, type, from_, to, time_, modified_since, resource_id)[offset:offset + limit]


    async def get_incident(
        self : "DemoAdapter",
        id : str
        ) -> status_models.Incident:
        return status_models.Incident.find_by_id(self.incidents, id)


    async def get_capabilities(
        self : "DemoAdapter",
        ) -> list[account_models.Capability]:
        return self.capabilities.values()
    

    def get_current_user(
            self : "DemoAdapter",
            request: Request,
            api_key: str
        ) -> str:
        """
            In a real deployment, this would decode the api_key jwt and return the current user's id.
            This method is not async.
        """
        return "gtorok"


    async def get_user(
            self : "DemoAdapter",
            request: Request,
            user_id: str
            ) -> account_models.User:
        return self.user


    async def get_projects(
            self : "DemoAdapter",
            request: Request,
            user: account_models.User
            ) -> list[account_models.Project]:
        return self.projects
    

    async def get_project_allocations(
        self : "DemoAdapter",
        request: Request,
        project: account_models.Project,
        user: account_models.User
        ) -> list[account_models.ProjectAllocation]:
        return [pa for pa in self.project_allocations if pa.project_id == project.id]
    

    async def get_user_allocations(
        self : "DemoAdapter",
        request: Request,
        user: account_models.User,
        project_allocation: account_models.ProjectAllocation,
        ) -> list[account_models.UserAllocation]:
        return [ua for ua in self.user_allocations if ua.project_allocation_id == project_allocation.id]


    async def submit_job(
        self: "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        job: psij.Job,
    ) -> compute_models.Job:
        return compute_models.Job(
            id="job_123",
            status=compute_models.JobStatus(
                state=psij.JobState.NEW,
                time=time.time(),
                message="job submitted",
                exit_code=None,
                meta_data={ "account": "account1" },
            )
        )
    

    async def get_job(
        self: "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        job_id: str,
    ) -> compute_models.Job:
        return compute_models.Job(
            id=job_id,
            status=compute_models.JobStatus(
                state=psij.JobState.COMPLETED,
                time=time.time(),
                message="job completed successfully",
                exit_code=0,
                meta_data={ "account": "account1" },
            )
        )


    async def get_jobs(
        self: "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        offset : int,
        limit : int,
        filters: dict[str, object] | None = None,
    ) -> list[compute_models.Job]:
        return [compute_models.Job(
            id=f"job_{i}",
            status=compute_models.JobStatus(
                state=random.choice([s for s in psij.JobState]),
                time=time.time() - (random.random() * 100),
                message="",
                exit_code=random.choice([0, 0, 0, 0, 0, 1, 1, 128, 127]),
                meta_data={ "account": "account1" },
            )
        ) for i in range(random.randint(3, 10))]
    

    async def cancel_job(
        self: "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        job_id: str,
    ) -> bool:
        # call slurm/etc. to cancel job
        return True