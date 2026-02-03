import os
from abc import abstractmethod
from typing import Any, Tuple
from ..status import models as status_models
from ..account import models as account_models
from . import models as filesystem_models
from ..iri_router import AuthenticatedAdapter


def to_int(name, default_value):
    try:
        return int(os.environ.get(name) or default_value)
    except:
        return default_value


OPS_SIZE_LIMIT = to_int("OPS_SIZE_LIMIT", 5 * 1024 * 1024)


class FacilityAdapter(AuthenticatedAdapter):
    """
    Facility-specific code is handled by the implementation of this interface.
    Use the `IRI_API_ADAPTER` environment variable (defaults to `app.demo_adapter.FacilityAdapter`)
    to install your facility adapter before the API starts.
    """

    @abstractmethod
    async def chmod(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        request_model: filesystem_models.PutFileChmodRequest,
        **kwargs
    ) -> filesystem_models.PutFileChmodResponse:
        pass


    @abstractmethod
    async def chown(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        request_model: filesystem_models.PutFileChownRequest,
        **kwargs
    ) -> filesystem_models.PutFileChownResponse:
        pass


    @abstractmethod
    async def ls(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        path: str,
        show_hidden: bool,
        numeric_uid: bool,
        recursive: bool,
        dereference: bool,
        **kwargs
    ) -> filesystem_models.GetDirectoryLsResponse:
        pass


    @abstractmethod
    async def head(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        path: str,
        file_bytes: int,
        lines: int,
        skip_trailing: bool,
        **kwargs
    ) -> Tuple[Any, int]:
        pass


    @abstractmethod
    async def tail(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        path: str,
        file_bytes: int | None,
        lines: int | None,
        skip_trailing: bool,
        **kwargs
    ) -> Tuple[Any, int]:
        pass


    @abstractmethod
    async def view(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        path: str,
        size: int,
        offset: int,
        **kwargs
    ) -> filesystem_models.GetViewFileResponse:
        pass


    @abstractmethod
    async def checksum(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        path: str,
        **kwargs
    ) -> filesystem_models.GetFileChecksumResponse:
        pass


    @abstractmethod
    async def file(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        path: str,
        **kwargs
    ) -> filesystem_models.GetFileTypeResponse:
        pass


    @abstractmethod
    async def stat(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        path: str,
        dereference: bool,
        **kwargs
    ) -> filesystem_models.GetFileStatResponse:
        pass


    @abstractmethod
    async def rm(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        path: str,
        **kwargs
    ):
        pass


    @abstractmethod
    async def mkdir(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        request_model: filesystem_models.PostMakeDirRequest,
        **kwargs
    ) -> filesystem_models.PostMkdirResponse:
        pass


    @abstractmethod
    async def symlink(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        request_model: filesystem_models.PostFileSymlinkRequest,
        **kwargs
    ) -> filesystem_models.PostFileSymlinkResponse:
        pass


    @abstractmethod
    async def download(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        path: str,
        **kwargs
    ) -> Any:
        pass


    @abstractmethod
    async def upload(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        path: str,
        content: str,
        **kwargs
    ) -> None:
        pass


    @abstractmethod
    async def compress(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        request_model: filesystem_models.PostCompressRequest,
        **kwargs
    ) -> filesystem_models.PostCompressResponse:
        pass


    @abstractmethod
    async def extract(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        request_model: filesystem_models.PostExtractRequest,
        **kwargs
    ) -> filesystem_models.PostExtractResponse:
        pass


    @abstractmethod
    async def mv(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        request_model: filesystem_models.PostMoveRequest,
        **kwargs
    ) -> filesystem_models.PostMoveResponse:
        pass


    @abstractmethod
    async def cp(
        self : "FacilityAdapter",
        resource: status_models.Resource,
        user: account_models.User,
        request_model: filesystem_models.PostCopyRequest,
        **kwargs
    ) -> filesystem_models.PostCopyResponse:
        pass
