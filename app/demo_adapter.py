import datetime
import random
from .facility_adapter import FacilityAdapter
from .routers.status import models as status_models


class DemoAdapter(FacilityAdapter):
    def __init__(self):
        self.resources = []
        self.incidents = []
        self.events = []

        self._init_state()

    
    def _init_state(self):
        self.resources = [
            status_models.Resource(id="pm", name="perlmutter", description="the perlmutter computer"),
            status_models.Resource(id="hpss", name="hpss", description="hpss tape storage"),
            status_models.Resource(id="cfs", name="cfs", description="cfs storage"),
            status_models.Resource(id="iris", name="Iris", description="Iris webapp"),
            status_models.Resource(id="sfapi", name="sfapi", description="the Superfacility API"),
        ]
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
