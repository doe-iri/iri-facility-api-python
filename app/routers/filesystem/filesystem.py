# Copied from: https://github.com/eth-cscs/firecrest-v2/blob/master/src/firecrest/filesystem/ops/router.py
#
# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause
import base64
from fastapi import Depends, HTTPException, status, Request, File, UploadFile
from ...types.http import forbidExtraQueryParams
from ...types.user import User
from .. import iri_router
from ..error_handlers import DEFAULT_RESPONSES
from ..iri_meta import iri_meta_dict
from ..status.status import router as status_router, models as status_models
from ..task import facility_adapter as task_facility_adapter, models as task_models
from . import models, facility_adapter


router = iri_router.IriRouter(
    facility_adapter.FacilityAdapter,
    task_facility_adapter.FacilityAdapter,
    prefix="/filesystem",
    tags=["filesystem"],
)


@router.post(
    "/resources",
    response_model=list[status_models.Resource],
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="getFilesystemResources",
    openapi_extra=iri_meta_dict("planned"),
)
async def post_resources(
    request: Request,
    _forbid=Depends(forbidExtraQueryParams()),
):
    """Get a list of resources that can be used in this endpoint"""
    return await status_router.adapter.get_resources_for_endpoint(status_models.Endpoint.filesystem)


async def _user_resource(
    resource_id: str,
    user: User,
) -> status_models.Resource:
    resource = await status_router.adapter.get_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource


@router.post(
    "/chmod/{resource_id:str}",
    description="Change the permission mode of a file(`chmod`)",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="File permissions changed successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="chmod",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_chmod(
    resource_id: str,
    request_model: models.PutFileChmodRequest,
    request: Request,
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    resource = await _user_resource(resource_id, user)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="chmod",
            args={"request_model": request_model},
        ),
    )


@router.post(
    "/chown/{resource_id:str}",
    description="Change the ownership of a given file (`chown`)",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="File ownership changed successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="chown",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_chown(
    resource_id: str,
    request_model: models.PutFileChownRequest,
    request: Request,
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    resource = await _user_resource(resource_id, user)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="chown",
            args={"request_model": request_model},
        ),
    )


@router.post(
    "/file/{resource_id:str}",
    description="Output the type of a file or directory",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="Type returned successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="file",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_file(
    resource_id: str,
    request_model: models.PostFileRequest,
    request: Request,
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    resource = await _user_resource(resource_id, user)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="file",
            args={"path": request_model.path},
        ),
    )


@router.post(
    "/stat/{resource_id:str}",
    description="Output the `stat` of a file",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="Stat returned successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="stat",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_stat(
    resource_id: str,
    request_model: models.PostStatRequest,
    request: Request,
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    resource = await _user_resource(resource_id, user)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="stat",
            args={"path": request_model.path, "dereference": request_model.dereference},
        ),
    )


@router.post(
    "/mkdir/{resource_id:str}",
    description="Create directory operation (`mkdir`)",
    status_code=status.HTTP_201_CREATED,
    response_model=task_models.TaskSubmitResponse,
    response_description="Directory created successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="mkdir",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_mkdir(
    resource_id: str,
    request: Request,
    request_model: models.PostMakeDirRequest,
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    resource = await _user_resource(resource_id, user)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="mkdir",
            args={"request_model": request_model},
        ),
    )


@router.post(
    "/symlink/{resource_id:str}",
    description="Create symlink operation (`ln`)",
    status_code=status.HTTP_201_CREATED,
    response_model=task_models.TaskSubmitResponse,
    response_description="Symlink created successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="symlink",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_symlink(
    resource_id: str,
    request: Request,
    request_model: models.PostFileSymlinkRequest,
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    resource = await _user_resource(resource_id, user)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="symlink",
            args={"request_model": request_model},
        ),
    )


@router.post(
    "/ls/{resource_id:str}",
    description="List the contents of the given directory (`ls`) asynchronously",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="Directory listed successfully",
    include_in_schema=router.task_adapter is not None,
    responses=DEFAULT_RESPONSES,
    operation_id="ls",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_ls(
    resource_id: str,
    request_model: models.PostLsRequest,
    request: Request,
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    resource = await _user_resource(resource_id, user)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="ls",
            args={
                "path": request_model.path,
                "show_hidden": request_model.show_hidden,
                "numeric_uid": request_model.numeric_uid,
                "recursive": request_model.recursive,
                "dereference": request_model.dereference,
            },
        ),
    )


@router.post(
    "/head/{resource_id:str}",
    description="Output the first part of file/s (`head`)",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="Head operation finished successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="head",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_head(
    resource_id: str,
    request_model: models.PostHeadRequest,
    request: Request,
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    if (request_model.file_bytes is None and request_model.lines is None) or (request_model.file_bytes is not None and request_model.lines is not None):
        raise HTTPException(status_code=400, detail="Exactly one of `bytes` or `lines` must be specified.")
    resource = await _user_resource(resource_id, user)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="head",
            args={
                "path": request_model.path,
                "file_bytes": request_model.file_bytes,
                "lines": request_model.lines,
                "skip_trailing": request_model.skip_trailing,
            },
        ),
    )


@router.post(
    "/view/{resource_id:str}",
    description=f"View file content (up to max {facility_adapter.OPS_SIZE_LIMIT} bytes)",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="View operation finished successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="view",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_view(
    resource_id: str,
    request_model: models.PostViewRequest,
    request: Request,
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    if request_model.size > facility_adapter.OPS_SIZE_LIMIT:
        raise HTTPException(status_code=400, detail=f"Requested size exceeds limit of {facility_adapter.OPS_SIZE_LIMIT} bytes.")
    resource = await _user_resource(resource_id, user)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="view",
            args={"path": request_model.path, "size": request_model.size, "offset": request_model.offset},
        ),
    )


@router.post(
    "/tail/{resource_id:str}",
    description="Output the last part of a file (`tail`)",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="`tail` operation finished successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="tail",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_tail(
    resource_id: str,
    request_model: models.PostTailRequest,
    request: Request,
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    if (request_model.file_bytes is None and request_model.lines is None) or (request_model.file_bytes is not None and request_model.lines is not None):
        raise HTTPException(status_code=400, detail="Exactly one of `bytes` or `lines` must be specified.")
    resource = await _user_resource(resource_id, user)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="tail",
            args={
                "path": request_model.path,
                "file_bytes": request_model.file_bytes,
                "lines": request_model.lines,
                "skip_heading": request_model.skip_heading,
            },
        ),
    )


@router.post(
    "/checksum/{resource_id:str}",
    description="Output the checksum of a file (using SHA-256 algorithm)",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="Checksum returned successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="checksum",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_checksum(
    resource_id: str,
    request_model: models.PostChecksumRequest,
    request: Request,
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    resource = await _user_resource(resource_id, user)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="checksum",
            args={"path": request_model.path},
        ),
    )


@router.post(
    "/rm/{resource_id:str}",
    description="Delete file or directory operation (`rm`)",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="File or directory deleted successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="rm",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_rm(
    resource_id: str,
    request_model: models.PostRmRequest,
    request: Request,
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    resource = await _user_resource(resource_id, user)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="rm",
            args={"path": request_model.path},
        ),
    )


@router.post(
    "/compress/{resource_id:str}",
    description="Compress files and directories using `tar` command",
    status_code=status.HTTP_201_CREATED,
    response_model=task_models.TaskSubmitResponse,
    response_description="File and/or directories compressed successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="compress",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_compress(
    resource_id: str,
    request: Request,
    request_model: models.PostCompressRequest,
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    resource = await _user_resource(resource_id, user)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="compress",
            args={"request_model": request_model},
        ),
    )


@router.post(
    "/extract/{resource_id:str}",
    description="Extract `tar` `gzip` archives",
    status_code=status.HTTP_201_CREATED,
    response_model=task_models.TaskSubmitResponse,
    response_description="File extracted successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="extract",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_extract(
    resource_id: str,
    request: Request,
    request_model: models.PostExtractRequest,
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    resource = await _user_resource(resource_id, user)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="extract",
            args={"request_model": request_model},
        ),
    )


@router.post(
    "/mv/{resource_id:str}",
    description="Create move file or directory operation (`mv`)",
    status_code=status.HTTP_201_CREATED,
    response_model=task_models.TaskSubmitResponse,
    response_description="Move file or directory operation created successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="mv",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_mv(
    resource_id: str,
    request: Request,
    request_model: models.PostMoveRequest,
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    resource = await _user_resource(resource_id, user)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="mv",
            args={"request_model": request_model},
        ),
    )


@router.post(
    "/cp/{resource_id:str}",
    description="Create copy file or directory operation (`cp`)",
    status_code=status.HTTP_201_CREATED,
    response_model=task_models.TaskSubmitResponse,
    response_description="Copy file or directory operation created successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="cp",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_cp(
    resource_id: str,
    request: Request,
    request_model: models.PostCopyRequest,
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    resource = await _user_resource(resource_id, user)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="cp",
            args={"request_model": request_model},
        ),
    )


@router.post(
    "/download/{resource_id:str}",
    description=f"Download a small file (max {facility_adapter.OPS_SIZE_LIMIT} Bytes)",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="File downloaded successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="download",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_download(
    resource_id: str,
    request_model: models.PostDownloadRequest,
    request: Request,
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    resource = await _user_resource(resource_id, user)
    return await router.task_adapter.put_task(
        user=user,
        resource=resource,
        task=task_models.TaskCommand(
            router=router.get_router_name(),
            command="download",
            args={"path": request_model.path},
        ),
    )


@router.post(
    "/upload/{resource_id:str}",
    description=f"Upload a small file (max {facility_adapter.OPS_SIZE_LIMIT} Bytes)",
    status_code=status.HTTP_200_OK,
    response_model=task_models.TaskSubmitResponse,
    response_description="File uploaded successfully",
    responses=DEFAULT_RESPONSES,
    operation_id="upload",
    openapi_extra=iri_meta_dict("production", "required")
)
async def post_upload(
    resource_id: str,
    request: Request,
    path: str,
    file: UploadFile = File(description="File to be uploaded as `multipart/form-data`"),
    user: User = Depends(router.current_user),
) -> task_models.TaskSubmitResponse:
    resource = await _user_resource(resource_id, user)
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
