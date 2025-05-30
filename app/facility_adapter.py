from fastapi import Request
from abc import ABC, abstractmethod
from .routers.status import models as status_models
from .routers.account import models as account_models
import datetime


class FacilityAdapter(ABC):
    """
    Facility-specific code is handled by the implementation of this interface.
    Use the `IRI_API_ADAPTER` environment variable (defaults to `app.demo_adapter.FacilityAdapter`) 
    to install your facility adapter before the API starts.
    """


    @abstractmethod
    def get_resources(
        self : "FacilityAdapter",
        name : str | None = None,
        description : str | None = None
        ) -> list[status_models.Resource]:
        pass


    @abstractmethod
    def get_resource(
        self : "FacilityAdapter",
        id : str
        ) -> status_models.Resource:
        pass


    @abstractmethod
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


    @abstractmethod
    def get_events(
        self : "FacilityAdapter",
        name : str | None = None,
        description : str | None = None,
        status : status_models.Status | None = None,
        start : datetime.datetime | None = None,
        end : datetime.datetime | None = None
        ) -> list[status_models.Event]:
        pass


    @abstractmethod
    def get_event(
        self : "FacilityAdapter",
        id : str
        ) -> status_models.Event:
        pass


    @abstractmethod
    def get_incidents(
        self : "FacilityAdapter",
        name : str | None = None,
        description : str | None = None,
        status : status_models.Status | None = None,
        type : status_models.IncidentType | None = None,
        start : datetime.datetime | None = None,
        end : datetime.datetime | None = None
        ) -> list[status_models.Incident]:
        pass


    @abstractmethod
    def get_incident(
        self : "FacilityAdapter",
        id : str
        ) -> status_models.Incident:
        pass


    @abstractmethod
    def get_capabilities(
        self : "FacilityAdapter",
        ) -> list[account_models.Capability]:
        pass


    @abstractmethod
    def get_current_user(
        self : "FacilityAdapter",
        request: Request,
        api_key: str
        ) -> str:
        """
            Decode the api_key and return the authenticated user's id.
            This method is not called directly, rather authorized endpoints "depend" on it.
            (https://fastapi.tiangolo.com/tutorial/dependencies/)
        """
        pass


    @abstractmethod
    def get_user(
        self : "FacilityAdapter",
        user_id: str
        ) -> account_models.User:
        pass


    @abstractmethod
    def get_projects(
        self : "FacilityAdapter",
        user: account_models.User
        ) -> list[account_models.Project]:
        pass


    @abstractmethod
    def get_project_allocations(
        self : "FacilityAdapter",
        project: account_models.Project
        ) -> list[account_models.ProjectAllocation]:
        pass


    @abstractmethod
    def get_user_allocations(
        self : "FacilityAdapter",
        user: account_models.User,
        project_allocations: list[account_models.ProjectAllocation],
        ) -> list[account_models.UserAllocation]:
        pass
