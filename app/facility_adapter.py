from .routers.status import models as status_models
import datetime

class FacilityAdapter:
    """
    Facility-specific code is handled by the implementation of this interface.
    Use the `IRI_API_ADAPTER` environment variable (defaults to `app.demo_adapter.FacilityAdapter`) 
    to install your facility adapter before the API starts.
    """


    def get_resources(
        self : "FacilityAdapter",
        name : str | None = None,
        description : str | None = None
        ) -> list[status_models.Resource]:
        pass


    def get_resource(
        self : "FacilityAdapter",
        id : str
        ) -> status_models.Resource:
        pass


    def get_events_resource(
        self : "FacilityAdapter",
        resource_id : str,
        name : str | None = None,
        description : str | None = None,
        status : status_models.Status | None = None,
        start : datetime.datetime | None = None,
        end : datetime.datetime | None = None
        ) -> list[status_models.Event]:
        pass


    def get_events(
        self : "FacilityAdapter",
        name : str | None = None,
        description : str | None = None,
        status : status_models.Status | None = None,
        start : datetime.datetime | None = None,
        end : datetime.datetime | None = None
        ) -> list[status_models.Event]:
        pass


    def get_event(
        self : "FacilityAdapter",
        id : str
        ) -> status_models.Event:
        pass


    def get_incidents(
        self : "FacilityAdapter",
        name : str | None = None,
        description : str | None = None,
        status : status_models.Status | None = None,
        type : status_models.IncidentType | None = None,
        start : datetime.datetime | None = None,
        end : datetime.datetime | None = None
        ) -> list[status_models.IncidentResponse]:
        pass


    def get_incident(
        self : "FacilityAdapter",
        id : str
        ) -> status_models.Incident:
        pass
