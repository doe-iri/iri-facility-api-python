from fastapi import Request
from abc import ABC, abstractmethod
from .routers.status import models as status_models
from .routers.account import models as account_models
import datetime
import psij


class FacilityAdapter(ABC):
    """
    Facility-specific code is handled by the implementation of this interface.
    Use the `IRI_API_ADAPTER` environment variable (defaults to `app.demo_adapter.FacilityAdapter`) 
    to install your facility adapter before the API starts.
    """


    @abstractmethod
    def get_resources(
        self : "FacilityAdapter",
        offset : int,
        limit : int,
        name : str | None = None,
        description : str | None = None,        
        group : str | None = None,
        resource_type : status_models.ResourceType | None = None,
        ) -> list[status_models.Resource]:
        pass


    @abstractmethod
    def get_resource(
        self : "FacilityAdapter",
        id : str
        ) -> status_models.Resource:
        pass


    @abstractmethod
    def get_events(
        self : "FacilityAdapter",
        incident_id : str,
        offset : int,
        limit : int,
        resource_id : str | None = None,
        name : str | None = None,
        description : str | None = None,
        status : status_models.Status | None = None,
        from_ : datetime.datetime | None = None,
        to : datetime.datetime | None = None,
        time : datetime.datetime | None = None
        ) -> list[status_models.Event]:
        pass


    @abstractmethod
    def get_event(
        self : "FacilityAdapter",
        incident_id : str,
        id : str
        ) -> status_models.Event:
        pass


    @abstractmethod
    def get_incidents(
        self : "FacilityAdapter",
        offset : int,
        limit : int,
        name : str | None = None,
        description : str | None = None,
        status : status_models.Status | None = None,
        type : status_models.IncidentType | None = None,
        from_ : datetime.datetime | None = None,
        to : datetime.datetime | None = None,
        time_ : datetime.datetime | None = None,
        updated_since : datetime.datetime | None = None,
        resource_id : str | None = None,
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
        request: Request,
        user_id: str
        ) -> account_models.User:
        pass


    @abstractmethod
    def get_projects(
        self : "FacilityAdapter",
        request: Request,
        user: account_models.User
        ) -> list[account_models.Project]:
        pass


    @abstractmethod
    def get_project_allocations(
        self : "FacilityAdapter",
        request: Request,
        project: account_models.Project
        ) -> list[account_models.ProjectAllocation]:
        pass


    @abstractmethod
    def get_user_allocations(
        self : "FacilityAdapter",
        request: Request,
        user: account_models.User,
        project_allocations: list[account_models.ProjectAllocation],
        ) -> list[account_models.UserAllocation]:
        pass

    
    @abstractmethod
    def submit_job(
        self: "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        job: psij.Job,
    ) -> psij.Job:
        pass

    
    @abstractmethod
    def get_job(
        self: "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        job_id: str,
    ) -> psij.Job:
        pass

    
    @abstractmethod
    def cancel_job(
        self: "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        job: psij.Job,
    ) -> bool:
        pass