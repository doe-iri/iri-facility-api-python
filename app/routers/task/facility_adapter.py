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
        cmd: task_models.TaskCommand,
    ) -> tuple[str, task_models.TaskStatus]:
        # Handle a task from the facility message queue.
        # Returns: (result, status)
        try:
            r = None
            if cmd.router == "filesystem":
                fs_adapter = IriRouter.create_adapter(cmd.router, filesystem_adapter.FacilityAdapter)
                if cmd.command == "chmod":
                    request_model = filesystem_models.PutFileChmodRequest.model_validate(cmd.args["request_model"])
                    o = await fs_adapter.chmod(resource, user, request_model)
                    r = o.model_dump_json()
                elif cmd.command == "chown":
                    request_model = filesystem_models.PutFileChownRequest.model_validate(cmd.args["request_model"])
                    o = await fs_adapter.chown(resource, user, request_model)
                    r = o.model_dump_json()
                elif cmd.command == "file":
                    o = await fs_adapter.file(resource, user, **cmd.args)
                    r = o.model_dump_json()
                elif cmd.command == "stat":
                    o = await fs_adapter.stat(resource, user, **cmd.args)
                    r = o.model_dump_json()
                elif cmd.command == "mkdir":
                    request_model = filesystem_models.PostMakeDirRequest.model_validate(cmd.args["request_model"])
                    o = await fs_adapter.mkdir(resource, user, request_model)
                    r = o.model_dump_json()
                elif cmd.command == "symlink":
                    request_model = filesystem_models.PostFileSymlinkRequest.model_validate(cmd.args["request_model"])
                    o = await fs_adapter.symlink(resource, user, request_model)
                    r = o.model_dump_json()
                elif cmd.command == "ls":
                    o = await fs_adapter.ls(resource, user, **cmd.args)
                    r = o.model_dump_json()
                elif cmd.command == "head":
                    o = await fs_adapter.head(resource, user, **cmd.args)
                    r = o.model_dump_json()
                elif cmd.command == "view":
                    o = await fs_adapter.view(resource, user, **cmd.args)
                    r = o.model_dump_json()
                elif cmd.command == "tail":
                    o = await fs_adapter.tail(resource, user, **cmd.args)
                    r = o.model_dump_json()
                elif cmd.command == "checksum":
                    o = await fs_adapter.checksum(resource, user, **cmd.args)
                    r = o.model_dump_json()
                elif cmd.command == "rm":
                    o = await fs_adapter.rm(resource, user, **cmd.args)
                    r = o.model_dump_json()
                elif cmd.command == "compress":
                    request_model = filesystem_models.PostCompressRequest.model_validate(cmd.args["request_model"])
                    o = await fs_adapter.compress(resource, user, request_model)
                    r = o.model_dump_json()
                elif cmd.command == "extract":
                    request_model = filesystem_models.PostExtractRequest.model_validate(cmd.args["request_model"])
                    o = await fs_adapter.extract(resource, user, request_model)
                    r = o.model_dump_json()
                elif cmd.command == "mv":
                    request_model = filesystem_models.PostMoveRequest.model_validate(cmd.args["request_model"])
                    o = await fs_adapter.mv(resource, user, request_model)
                    r = o.model_dump_json()
                elif cmd.command == "cp":
                    request_model = filesystem_models.PostCopyRequest.model_validate(cmd.args["request_model"])
                    o = await fs_adapter.cp(resource, user, request_model)
                    r = o.model_dump_json()
                elif cmd.command == "download":
                    r = await fs_adapter.download(resource, user, **cmd.args)
                elif cmd.command == "upload":
                    o = await fs_adapter.upload(resource, user, **cmd.args)
                    r = "File uploaded successfully"
            if r:
                return (r, task_models.TaskStatus.completed)
            else:
                return (f"Task was cancelled due to unknown router/command: {cmd.router}:{cmd.command}", task_models.TaskStatus.failed)
        except Exception as exc:
            return (f"Error: {exc}", task_models.TaskStatus.failed)
