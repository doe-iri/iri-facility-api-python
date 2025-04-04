from .routers.status import models
import datetime
import random

# simulated state data
class SimulatedState:
    def __init__(self):
        self.resources = []
        self.incidents = []
        self.events = []

        self._init_state()

    
    def _init_state(self):
        self.resources = [
            models.Resource(id="pm", name="perlmutter", description="the perlmutter computer"),
            models.Resource(id="hpss", name="hpss", description="hpss tape storage"),
            models.Resource(id="cfs", name="cfs", description="cfs storage"),
            models.Resource(id="iris", name="Iris", description="Iris webapp"),
            models.Resource(id="sfapi", name="sfapi", description="the Superfacility API"),
        ]
        statuses = { r.name: models.Status.up for r in self.resources }        
        last_incidents = {}
        d = datetime.datetime(2025, 3, 1, 10, 0, 0)

        # generate some events and incidents
        # here every incident only has events from a single resource, 
        # but in reality it is possible for an incident to have events from multiple resources
        for i in range(0, 1000):
            r = random.choice(self.resources)
            status = statuses[r.name]
            event = models.Event(
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
                if status == models.Status.up:
                    incident = last_incidents[r.name]
                    incident.end = d
                    del last_incidents[r.name]
            
            if random.random() > 0.9:
                if status == models.Status.down:
                    statuses[r.name] = models.Status.up
                else:
                    statuses[r.name] = models.Status.down
                    dstr = d.strftime("%Y-%m-%d %H:%M:%S.%f%z")
                    incident = models.Incident(
                        id=f"inc{len(self.incidents)}", 
                        name=f"{r.name} incident at {dstr}", 
                        description=f"{r.name} incident at {dstr}", 
                        status=models.Status.down,
                        events=[],
                        start=d,
                        end=d,
                        type=random.choice(list(models.IncidentType)),
                        resolution="PM was fixed by NERSC staff"
                    )
                    self.incidents.append(incident)
                    last_incidents[r.name] = incident
                    

            d += datetime.timedelta(minutes=int(random.random() * 15 + 1))

