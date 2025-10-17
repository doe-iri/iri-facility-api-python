from abc import ABC, abstractmethod
from ..status import models as status_models
from ..account import models as account_models
from . import models as filesystem_models
from typing import Any


class FacilityAdapter(ABC):
    """
    Facility-specific code is handled by the implementation of this interface.
    Use the `IRI_API_ADAPTER` environment variable (defaults to `app.demo_adapter.FacilityAdapter`) 
    to install your facility adapter before the API starts.
    """


    @abstractmethod
    def get_current_user(
        self : "FacilityAdapter",
        api_key: str,
        ip_address: str,
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
        user_id: str,
        api_key: str,
        ) -> account_models.User:
        pass


    @abstractmethod
    def chmod(
        self : "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        request_model: filesystem_models.PutFileChmodRequest
    ) -> filesystem_models.PutFileChmodResponse:
        pass


    @abstractmethod
    def chown(
        self : "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        request_model: filesystem_models.PutFileChownRequest
    ) -> filesystem_models.PutFileChownResponse:
        pass


    @abstractmethod
    def ls(
        self : "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str, 
        show_hidden: bool, 
        numeric_uid: bool, 
        recursive: bool, 
        dereference: bool,
    ) -> Any:
        pass


    @abstractmethod
    def head(
        self : "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str, 
        file_bytes: int, 
        lines: int, 
        skip_trailing: bool,
    ) -> Any:
        pass


    @abstractmethod
    def view(
        self : "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str, 
        size: int,
        offset: int,
    ) -> Any:
        pass


    @abstractmethod
    def checksum(
        self : "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str, 
    ) -> Any:
        pass


    @abstractmethod
    def file(
        self : "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str, 
    ) -> Any:
        pass


    @abstractmethod
    def stat(
        self : "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str, 
        dereference: bool,
    ) -> Any:
        pass


    @abstractmethod
    def rm(
        self : "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str, 
    ):
        pass


    @abstractmethod
    def mkdir(
        self : "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        request_model: filesystem_models.PostMakeDirRequest,
    ) -> filesystem_models.PostMkdirResponse:
        pass


    @abstractmethod
    def symlink(
        self : "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        request_model: filesystem_models.PostFileSymlinkRequest,
    ) -> filesystem_models.PostFileSymlinkResponse:
        pass


    @abstractmethod
    def download(
        self : "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str,
    ) -> Any:
        pass


    @abstractmethod
    def upload(
        self : "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str,
        content: str,
    ) -> None:
        pass


    @abstractmethod
    def compress(
        self : "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        request_model: filesystem_models.PostCompressRequest,
    ) -> filesystem_models.PostCompressResponse:
        pass


    @abstractmethod
    def extract(
        self : "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        request_model: filesystem_models.PostExtractRequest,
    ) -> filesystem_models.PostExtractResponse:
        pass


    @abstractmethod
    def mv(
        self : "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        request_model: filesystem_models.PostMoveRequest,
    ) -> filesystem_models.PostMoveResponse:
        pass


    @abstractmethod
    def cp(
        self : "FacilityAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        request_model: filesystem_models.PostCopyRequest,
    ) -> filesystem_models.PostCopyResponse:
        pass
