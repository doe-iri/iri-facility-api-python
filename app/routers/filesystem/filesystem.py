# Copied from: https://github.com/eth-cscs/firecrest-v2/blob/master/src/firecrest/filesystem/ops/router.py
#
# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause
import base64
from typing import Annotated
from fastapi import Depends, HTTPException, status, Query, Request, File, UploadFile
from .. import iri_router
from ..error_handlers import DEFAULT_RESPONSES
from ..status.status import router as status_router, models as status_models
from ..account.account import models as account_models
from ..task import facility_adapter as task_facility_adapter, models as task_models
from . import models, facility_adapter


router = iri_router.IriRouter(
    facility_adapter.FacilityAdapter,
    task_facility_adapter.FacilityAdapter,
    prefix="/filesystem",
    tags=["filesystem"],
)


async def _user_resource(
    resource_id: str,
    request: Request,
) -> tuple[account_models.User, status_models.Resource]:
    user = await router.adapter.get_user(user_id=request.state.current_user_id, api_key=request.state.api_key, client_ip=iri_router.get_client_ip(request))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # look up the resource (todo: maybe ensure it's available)
    resource = await status_router.adapter.get_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return (user, resource)


@router.put(
    "/chmod/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Change the permission mode of a file(`chmod`)",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="File permissions changed successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="chmod",
)
async def put_chmod(
    resource_id: str,
    request_model: models.PutFileChmodRequest,
    request: Request,
) -> task_models.TaskSubmitResponse:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="chmod",
            args={
                "request_model": request_model,
            },
        ),
    )


@router.put(
    "/chown/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Change the ownership of a given file (`chown`)",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="File ownership changed successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="chown",
)
async def put_chown(
    resource_id: str,
    request_model: models.PutFileChownRequest,
    request: Request,
) -> task_models.TaskSubmitResponse:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="chown",
            args={
                "request_model": request_model,
            },
        ),
    )


@router.get(
    "/file/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Output the type of a file or directory",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="Type returned successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="file",
)
async def get_file(
    resource_id: str,
    request: Request,
    path: Annotated[str, Query(description="A file or folder path")],
) -> task_models.TaskSubmitResponse:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="file",
            args={
                "path": path,
            },
        ),
    )


@router.get(
    "/stat/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Output the `stat` of a file",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="Stat returned successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="stat",
)
async def get_stat(
    resource_id: str,
    request: Request,
    path: Annotated[str, Query(description="A file or folder path")],
    dereference: Annotated[bool, Query(description="Follow symbolic links")] = False,
) -> task_models.TaskSubmitResponse:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="stat",
            args={
                "path": path,
                "dereference": dereference,
            },
        ),
    )


@router.post(
    "/mkdir/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Create directory operation (`mkdir`)",
    status_code=status.HTTP_201_CREATED,
    response_model=task_models.TaskSubmitResponse,
    response_description="Directory created successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="mkdir",
)
async def post_mkdir(
    resource_id: str,
    request: Request,
    request_model: models.PostMakeDirRequest,
) -> task_models.TaskSubmitResponse:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="mkdir",
            args={
                "request_model": request_model,
            },
        ),
    )


@router.post(
    "/symlink/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Create symlink operation (`ln`)",
    status_code=status.HTTP_201_CREATED,
    response_model=task_models.TaskSubmitResponse,
    response_description="Symlink created successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="symlink",
)
async def post_symlink(
    resource_id: str,
    request: Request,
    request_model: models.PostFileSymlinkRequest,
) -> task_models.TaskSubmitResponse:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="symlink",
            args={
                "request_model": request_model,
            },
        ),
    )


@router.get(
    "/ls/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="List the contents of the given directory (`ls`) asynchronously",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="Directory listed successfully",
    include_in_schema=router.task_adapter is not None,
    responses=DEFAULT_RESPONSES,
    operation_id="ls",
)
async def get_ls_async(
    resource_id: str,
    request: Request,
    path: Annotated[str, Query(description="The path to list")],
    show_hidden: Annotated[bool, Query(alias="showHidden", description="Show hidden files")] = False,
    numeric_uid: Annotated[bool, Query(alias="numericUid", description="List numeric user and group IDs")] = False,
    recursive: Annotated[bool, Query(alias="recursive", description="Recursively list files and folders")] = False,
    dereference: Annotated[
        bool,
        Query(
            alias="dereference",
            description="Show information for the file the link references.",
        ),
    ] = False,
) -> task_models.TaskSubmitResponse:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(), 
            command="ls",
            args={"path": path, "show_hidden": show_hidden, "numeric_uid": numeric_uid, "recursive": recursive, "dereference": dereference}
        ),
    )


@router.get(
    "/head/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Output the first part of file/s (`head`)",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="Head operation finished successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="head",
)
async def get_head(
    resource_id: str,
    request: Request,
    path: Annotated[str, Query(description="File path")],
    # TODO Should we allow bytes and lines to be strings? The head allows the following:
    #    NUM may have a multiplier suffix: b 512, kB 1000, K 1024, MB
    #    1000*1000, M 1024*1024, GB 1000*1000*1000, G 1024*1024*1024, and
    #    so on for T, P, E, Z, Y, R, Q.  Binary prefixes can be used, too:
    #    KiB=K, MiB=M, and so on.
    file_bytes: Annotated[
        int,
        Query(
            alias="bytes",
            description="The output will be the first NUM bytes of each file.",
        ),
    ] = None,
    lines: Annotated[
        int,
        Query(
            description="The output will be the first NUM lines of each file.",
        ),
    ] = None,
    skip_trailing: Annotated[
        bool,
        Query(
            alias="skipTrailing",
            description=("The output will be the whole file, without the last NUM bytes/lines of each file. NUM should be specified in the respective argument through `bytes` or `lines`."),
        ),
    ] = False,
) -> task_models.TaskSubmitResponse:
    user, resource = await _user_resource(resource_id, request)
    # Enforce that exactly one of `bytes` or `lines` is specified
    if (file_bytes is None and lines is None) or (file_bytes is not None and lines is not None):
        raise HTTPException(status_code=400, detail="Exactly one of `bytes` or `lines` must be specified.")
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="head",
            args={
                "path": path,
                "file_bytes": file_bytes,
                "lines": lines,
                "skip_trailing": skip_trailing,
            },
        ),
    )


@router.get(
    "/view/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description=f"View file content (up to max {facility_adapter.OPS_SIZE_LIMIT} bytes)",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="View operation finished successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="view",
)
async def get_view(
    resource_id: str,
    request: Request,
    path: Annotated[str, Query(description="File path")],
    size: Annotated[int, Query(description="Value, in bytes, of the size of data to be retrieved from the file.", ge=1, le=facility_adapter.OPS_SIZE_LIMIT)] = facility_adapter.OPS_SIZE_LIMIT,
    offset: Annotated[int, Query(description="Value in bytes of the offset.", ge=0)] = 0,
) -> task_models.TaskSubmitResponse:
    user, resource = await _user_resource(resource_id, request)

    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="view",
            args={
                "path": path,
                "size": size,
                "offset": offset,
            },
        ),
    )


@router.get(
    "/tail/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Output the last part of a file (`tail`)",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="`tail` operation finished successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="tail",
)
async def get_tail(
    resource_id: str,
    request: Request,
    path: Annotated[str, Query(description="File path", min_length=1)],
    file_bytes: Annotated[
        int,
        Query(alias="bytes", description="The output will be the last NUM bytes of each file.", ge=1),
    ] = None,
    lines: Annotated[
        int,
        Query(
            description="The output will be the last NUM lines of each file.",
            ge=1,
        ),
    ] = None,
    skip_heading: Annotated[
        bool,
        Query(
            alias="skipHeading",
            description=("The output will be the whole file, without the first NUM bytes/lines of each file. NUM should be specified in the respective argument through `bytes` or `lines`."),
        ),
    ] = False,
) -> task_models.TaskSubmitResponse:
    user, resource = await _user_resource(resource_id, request)
    # Enforce that exactly one of `bytes` or `lines` is specified
    if (file_bytes is None and lines is None) or (file_bytes is not None and lines is not None):
        raise HTTPException(status_code=400, detail="Exactly one of `bytes` or `lines` must be specified.")
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="tail",
            args={
                "path": path,
                "file_bytes": file_bytes,
                "lines": lines,
                "skip_heading": skip_heading,
            },
        ),
    )


@router.get(
    "/checksum/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Output the checksum of a file (using SHA-256 algotithm)",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="Checksum returned successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="checksum",
)
async def get_checksum(
    resource_id: str,
    request: Request,
    path: Annotated[str, Query(description="Target system")],
) -> task_models.TaskSubmitResponse:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="checksum",
            args={
                "path": path,
            },
        ),
    )


@router.delete(
    "/rm/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Delete file or directory operation (`rm`)",
    response_description="File or directory deleted successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="rm",
)
async def delete_rm(
    resource_id: str,
    request: Request,
    path: Annotated[str, Query(description="The path to delete")],
) -> str:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="rm",
            args={
                "path": path,
            },
        ),
    )


@router.post(
    "/compress/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Compress files and directories using `tar` command",
    status_code=status.HTTP_201_CREATED,
    response_model=task_models.TaskSubmitResponse,
    response_description="File and/or directories compressed successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="compress",
)
async def post_compress(
    resource_id: str,
    request: Request,
    request_model: models.PostCompressRequest,
) -> task_models.TaskSubmitResponse:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="compress",
            args={
                "request_model": request_model,
            },
        ),
    )


@router.post(
    "/extract/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Extract `tar` `gzip` archives",
    status_code=status.HTTP_201_CREATED,
    response_model=task_models.TaskSubmitResponse,
    response_description="File extracted successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="extract",
)
async def post_extract(
    resource_id: str,
    request: Request,
    request_model: models.PostExtractRequest,
) -> task_models.TaskSubmitResponse:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="extract",
            args={
                "request_model": request_model,
            },
        ),
    )


@router.post(
    "/mv/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Create move file or directory operation (`mv`)",
    status_code=status.HTTP_201_CREATED,
    response_model=task_models.TaskSubmitResponse,
    response_description="Move file or directory operation created successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="mv",
)
async def move_mv(
    resource_id: str,
    request: Request,
    request_model: models.PostMoveRequest,
) -> task_models.TaskSubmitResponse:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="mv",
            args={
                "request_model": request_model,
            },
        ),
    )


@router.post(
    "/cp/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Create copy file or directory operation (`cp`)",
    status_code=status.HTTP_201_CREATED,
    response_model=task_models.TaskSubmitResponse,
    response_description="Copy file or directory operation created successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="cp",
)
async def post_cp(
    resource_id: str,
    request: Request,
    request_model: models.PostCopyRequest,
) -> task_models.TaskSubmitResponse:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="cp",
            args={
                "request_model": request_model,
            },
        ),
    )


@router.get(
    "/download/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description=f"Download a small file (max {facility_adapter.OPS_SIZE_LIMIT} Bytes)",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="File downloaded successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="download",
)
async def get_download(
    resource_id: str,
    request: Request,
    path: Annotated[str, Query(description="A file to download")],
) -> task_models.TaskSubmitResponse:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="download",
            args={
                "path": path,
            },
        ),
    )


@router.post(
    "/upload/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description=f"Upload a small file (max {facility_adapter.OPS_SIZE_LIMIT} Bytes)",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="File uploaded successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="upload",
)
async def post_upload(
    resource_id: str,
    request: Request,
    path: Annotated[str, Query(description="Specify path where file should be uploaded.")],
    file: UploadFile = File(description="File to be uploaded as `multipart/form-data`"),
) -> task_models.TaskSubmitResponse:
    user, resource = await _user_resource(resource_id, request)
    raw_content = file.file.read()

    if len(raw_content) > facility_adapter.OPS_SIZE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File to upload is too large.",
        )

    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="upload",
            args={
                "path": path,
                "content": base64.b64encode(raw_content).decode("utf-8"),
            },
        ),
    )
