from abc import abstractmethod
from typing import Any
from . import models as task_models
from ..account import models as account_models
from ..status import models as status_models
from ..filesystem import models as filesystem_models, facility_adapter as filesystem_adapter
from ..iri_router import AuthenticatedAdapter, IriRouter


class FacilityAdapter(AuthenticatedAdapter):
    """
    Facility-specific code is handled by the implementation of this interface.
    Use the `IRI_API_ADAPTER` environment variable (defaults to `app.demo_adapter.FacilityAdapter`)
    to install your facility adapter before the API starts.
    """


    @abstractmethod
    async def get_task(
        self : "FacilityAdapter",
        user: account_models.User,
        task_id: str,
        ) -> task_models.Task|None:
        pass


    @abstractmethod
    async def get_tasks(
        self : "FacilityAdapter",
        user: account_models.User,
        ) -> list[task_models.Task]:
        pass


    @abstractmethod
    async def put_task(
        self: "FacilityAdapter",
        user: account_models.User,
        resource: status_models.Resource|None,
        command: task_models.TaskCommand
    ) -> str:
        pass


    @staticmethod
    async def on_task(
        resource: status_models.Resource,
        user: account_models.User,
        router: str,
        command: str,
        args: dict[str:Any],
    ) -> tuple[str, task_models.TaskStatus]:
        # Handle a task from the facility message queue.
        # Returns: (result, status)
        try:
            r = None
            if router == "filesystem":
                fs_adapter = IriRouter.create_adapter(router, filesystem_adapter.FacilityAdapter)
                if command == "chmod":
                    request_model = filesystem_models.PutFileChmodRequest.model_validate(args["request_model"])
                    o = await fs_adapter.chmod(resource, user, request_model)
                    r = o.model_dump_json()
                elif command == "chown":
                    request_model = filesystem_models.PutFileChownRequest.model_validate(args["request_model"])
                    o = await fs_adapter.chown(resource, user, request_model)
                    r = o.model_dump_json()
                elif command == "file":
                    o = await fs_adapter.file(resource, user, **args)
                    r = o.model_dump_json()
                elif command == "stat":
                    o = await fs_adapter.stat(resource, user, **args)
                    r = o.model_dump_json()
                elif command == "mkdir":
                    request_model = filesystem_models.PostMakeDirRequest.model_validate(args["request_model"])
                    o = await fs_adapter.mkdir(resource, user, request_model)
                    r = o.model_dump_json()
                elif command == "symlink":
                    request_model = filesystem_models.PostFileSymlinkRequest.model_validate(args["request_model"])
                    o = await fs_adapter.symlink(resource, user, request_model)
                    r = o.model_dump_json()
                elif command == "ls":
                    o = await fs_adapter.ls(resource, user, **args)
                    r = o.model_dump_json()
                elif command == "head":
                    o = await fs_adapter.head(resource, user, **args)
                    r = o.model_dump_json()
                elif command == "view":
                    o = await fs_adapter.view(resource, user, **args)
                    r = o.model_dump_json()
                elif command == "tail":
                    o = await fs_adapter.tail(resource, user, **args)
                    r = o.model_dump_json()
                elif command == "checksum":
                    o = await fs_adapter.checksum(resource, user, **args)
                    r = o.model_dump_json()
                elif command == "rm":
                    o = await fs_adapter.rm(resource, user, **args)
                    r = o.model_dump_json()
                elif command == "compress":
                    request_model = filesystem_models.PostCompressRequest.model_validate(args["request_model"])
                    o = await fs_adapter.compress(resource, user, request_model)
                    r = o.model_dump_json()
                elif command == "extract":
                    request_model = filesystem_models.PostExtractRequest.model_validate(args["request_model"])
                    o = await fs_adapter.extract(resource, user, request_model)
                    r = o.model_dump_json()
                elif command == "mv":
                    request_model = filesystem_models.PostMoveRequest.model_validate(args["request_model"])
                    o = await fs_adapter.mv(resource, user, request_model)
                    r = o.model_dump_json()
                elif command == "cp":
                    request_model = filesystem_models.PostCopyRequest.model_validate(args["request_model"])
                    o = await fs_adapter.cp(resource, user, request_model)
                    r = o.model_dump_json()
                elif command == "download":
                    r = await fs_adapter.download(resource, user, **args)
                elif command == "upload":
                    o = await fs_adapter.upload(resource, user, **args)
                    r = "File uploaded successfully"
            if r:
                return (r, task_models.TaskStatus.completed)
            else:
                return (f"Task was cancelled due to unknown router/command: {router}:{command}", task_models.TaskStatus.failed)
        except Exception as exc:
            return (f"Error: {exc}", task_models.TaskStatus.failed)
