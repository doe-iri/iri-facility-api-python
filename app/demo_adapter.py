from fastapi import Request
import datetime
import random
from .facility_adapter import FacilityAdapter
from .routers.status import models as status_models
from .routers.account import models as account_models


class DemoAdapter(FacilityAdapter):
    def __init__(self):
        self.resources = []
        self.incidents = []
        self.events = []
        self.capabilities = []
        self.user = account_models.User(id="gtorok", name="Gabor Torok")
        self.projects = []
        self.project_allocations = []
        self.user_allocations = []

        self._init_state()

    
    def _init_state(self):

        self.capabilities = [
            account_models.Capability(id="cpu", name="CPU Nodes", units=[account_models.AllocationUnit.node_hours]),
            account_models.Capability(id="gpu", name="GPU Nodes", units=[account_models.AllocationUnit.node_hours]),
            account_models.Capability(id="tape_storage", name="Tape Storage", units=[account_models.AllocationUnit.bytes, account_models.AllocationUnit.inodes]),
            account_models.Capability(id="gpfs_storage", name="GPFS Storage", units=[account_models.AllocationUnit.bytes, account_models.AllocationUnit.inodes]),
        ]

        pm = status_models.Resource(id="pm", name="perlmutter", description="the perlmutter computer", capability_ids=["cpu", "gpu"])
        hpss = status_models.Resource(id="hpss", name="hpss", description="hpss tape storage", capability_ids=["tape_storage"])
        cfs = status_models.Resource(id="cfs", name="cfs", description="cfs storage", capability_ids=["gpfs_storage"])

        self.resources = [
            pm,
            hpss,
            cfs,
            status_models.Resource(id="iris", name="Iris", description="Iris webapp", capability_ids=[]),
            status_models.Resource(id="sfapi", name="sfapi", description="the Superfacility API", capability_ids=[]),
        ]

        self.projects = [
            account_models.Project(
                id="staff",
                name="Staff research project",
                description="Compute and storage allocation for staff research use",
                user_ids=[ "gtorok" ],
            ),
            account_models.Project(
                id="test",
                name="Test project",
                description="Compute and storage allocation for testing use",
                user_ids=[ "gtorok" ],
            ),
        ]

        for p in self.projects:
            for c in self.capabilities:
                pa = account_models.ProjectAllocation(
                    id=f"{p.id}_{c.id}",
                    project_id=p.id,
                    capability_id=c.id,
                    entries=[
                        account_models.AllocationEntry(
                            id=f"{p.id}_{c.id}_{cu.name}",
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
                        id=f"{pa.id}_gtorok",
                        project_allocation_id=pa.id,
                        user_id="gtorok",
                        entries=[
                            account_models.AllocationEntry(
                                id=f"{a.id}_gtorok",
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
                id=f"ev{i}",
                name=f"{r.name} is {status.value}",
                description=f"{r.name} is {status.value}",
                timestamp=d,
                status=status,
                resource=r
            )
            self.events.append(event)
            if r.name in last_incidents:
                last_incidents[r.name].events.append(event)
                if status == status_models.Status.up:
                    incident = last_incidents[r.name]
                    incident.end = d
                    del last_incidents[r.name]
            
            if random.random() > 0.9:
                if status == status_models.Status.down:
                    statuses[r.name] = status_models.Status.up
                else:
                    statuses[r.name] = status_models.Status.down
                    dstr = d.strftime("%Y-%m-%d %H:%M:%S.%f%z")
                    incident = status_models.Incident(
                        id=f"inc{len(self.incidents)}", 
                        name=f"{r.name} incident at {dstr}", 
                        description=f"{r.name} incident at {dstr}", 
                        status=status_models.Status.down,
                        events=[],
                        start=d,
                        end=d,
                        type=random.choice(list(status_models.IncidentType)),
                        resolution="PM was fixed by NERSC staff"
                    )
                    self.incidents.append(incident)
                    last_incidents[r.name] = incident
                    

            d += datetime.timedelta(minutes=int(random.random() * 15 + 1))


    async def get_resources(
        self : "DemoAdapter",
        name : str | None = None,
        description : str | None = None
        ) -> list[status_models.Resource]:
        return status_models.Resource.find(self.resources, name, description)


    async def get_resource(
        self : "DemoAdapter",
        id : str
        ) -> status_models.Resource:
        return status_models.Resource.find_by_id(self.resources, id)


    async def get_events_resource(
        self : "DemoAdapter",
        resource_id : str,
        name : str | None = None,
        description : str | None = None,
        status : status_models.Status | None = None,
        start : datetime.datetime | None = None,
        end : datetime.datetime | None = None
        ) -> list[status_models.Event]:
        return status_models.Event.find(
            [e for e in self.events if e.resource.id == resource_id], 
            name, description, status, start, end)


    async def get_events(
        self : "DemoAdapter",
        name : str | None = None,
        description : str | None = None,
        status : status_models.Status | None = None,
        start : datetime.datetime | None = None,
        end : datetime.datetime | None = None
        ) -> list[status_models.Event]:
        return status_models.Event.find(self.events, name, description, status, start, end)


    async def get_event(
        self : "DemoAdapter",
        id : str
        ) -> status_models.Event:
        return status_models.Event.find_by_id(self.events, id)


    async def get_incidents(
        self : "DemoAdapter",
        name : str | None = None,
        description : str | None = None,
        status : status_models.Status | None = None,
        type : status_models.IncidentType | None = None,
        start : datetime.datetime | None = None,
        end : datetime.datetime | None = None
        ) -> list[status_models.Incident]:
        # exclude events
        ii = [status_models.Incident(
            id=i.id,
            name=i.name,
            description=i.description,
            start=i.start,
            end=i.end,
            status=i.status,
            resolution=i.resolution,
            type=i.type,
            events=None,
        ) for i in self.incidents]
        return status_models.Incident.find(ii, name, description, status, type, start, end)


    async def get_incident(
        self : "DemoAdapter",
        id : str
        ) -> status_models.Incident:
        return status_models.Incident.find_by_id(self.incidents, id)


    async def get_capabilities(
        self : "DemoAdapter",
        ) -> list[account_models.Capability]:
        return self.capabilities
    

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
        project: account_models.Project
        ) -> list[account_models.ProjectAllocation]:
        return [pa for pa in self.project_allocations if pa.project_id == project.id]
    

    async def get_user_allocations(
        self : "DemoAdapter",
        request: Request,
        user: account_models.User,
        project_allocations: list[account_models.ProjectAllocation],
        ) -> list[account_models.UserAllocation]:
        pa_ids = set([pa.id for pa in project_allocations])
        return [ua for ua in self.user_allocations if ua.project_allocation_id in pa_ids]
