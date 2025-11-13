# Copied from: https://github.com/eth-cscs/firecrest-v2/blob/master/src/firecrest/filesystem/ops/router.py
# 
# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from fastapi import (
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
    Query,
    Request
)
import os
from typing import Any, Annotated
from .. import iri_router
from ..status.status import router as status_router, models as status_models
from ..account.account import models as account_models
from .import models, facility_adapter
from ..task import facility_adapter as task_facility_adapter, models as task_models
from .filesystem import _user_resource

def to_int(name, default_value):
    try:
        return os.environ.get(name) or default_value
    except:
        return default_value
    

OPS_SIZE_LIMIT = to_int("OPS_SIZE_LIMIT", 5 * 1024 * 1024)


router = iri_router.IriRouter(
    facility_adapter.FacilityAdapter,
    task_facility_adapter.FacilityAdapter,
    prefix="/filesystem/async",
    tags=["filesystem"],
)


@router.get(
    "/ls/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="List the contents of the given directory (`ls`) asynchronously",
    status_code=status.HTTP_200_OK,
    response_model=str,
    response_description="Directory listed successfully",
    include_in_schema=router.task_adapter is not None
)
async def get_ls_async(
    resource_id: str,
    request : Request,
    path: Annotated[str, Query(description="The path to list")],
    show_hidden: Annotated[
        bool, Query(alias="showHidden", description="Show hidden files")
    ] = False,
    numeric_uid: Annotated[
        bool, Query(alias="numericUid", description="List numeric user and group IDs")
    ] = False,
    recursive: Annotated[
        bool, Query(alias="recursive", description="Recursively list files and folders")
    ] = False,
    dereference: Annotated[
        bool,
        Query(
            alias="dereference",
            description="Show information for the file the link references.",
        ),
    ] = False,
) -> str:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user, 
        resource, 
        task_models.TaskCommand(
            router=router.get_router_name(),
            command="ls",
            args={
                "path": path,
                "show_hidden": show_hidden,
                "numeric_uid": numeric_uid,
                "recursive": recursive,
                "dereference": dereference
            }
        )
    )


@router.get(
    "/head/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Output the first part of file/s (`head`)",
    status_code=status.HTTP_200_OK,
    response_model=str,
    response_description="Head operation finished successfully",
)
async def get_head(
    resource_id: str,
    request : Request,
    path: Annotated[str, Query(description="File path")],
    # TODO Should we allow bytes and lines to be strings? The head allows the following:
    #    NUM may have a multiplier suffix: b 512, kB 1000, K 1024, MB
    #    1000*1000, M 1024*1024, GB 1000*1000*1000, G 1024*1024*1024, and
    #    so on for T, P, E, Z, Y, R, Q.  Binary prefixes can be used, too:
    #    KiB=K, MiB=M, and so on.
    file_bytes: Annotated[
        int | None,
        Query(
            alias="bytes",
            description="The output will be the first NUM bytes of each file.",
        ),
    ] = None,
    lines: Annotated[
        int | None,
        Query(
            description="The output will be the first NUM lines of each file.",
        ),
    ] = None,
    skip_trailing: Annotated[
        bool,
        Query(
            alias="skipTrailing",
            description=(
                "The output will be the whole file, without the last NUM "
                "bytes/lines of each file. NUM should be specified in the "
                "respective argument through `bytes` or `lines`."
            ),
        ),
    ] = False,
) -> str:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user, 
        resource, 
        task_models.TaskCommand(
            router=router.get_router_name(),
            command="head",
            args={
                "path": path,
                "file_bytes": file_bytes,
                "lines": lines,
                "skip_trailing": skip_trailing,
            }
        )
    )


@router.get(
    "/view/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description=f"View file content (up to max {OPS_SIZE_LIMIT} bytes)",
    status_code=status.HTTP_200_OK,
    response_model=str,
    response_description="View operation finished successfully",
)
async def get_view(
    resource_id: str,
    request : Request,
    path: Annotated[str, Query(description="File path")],
    size: Annotated[
        int | None,
        Query(
            alias="size",
            description="Value, in bytes, of the size of data to be retrieved from the file.",
        ),
    ] = OPS_SIZE_LIMIT,
    offset: Annotated[
        int | None,
        Query(
            alias="offset",
            description="Value in bytes of the offset.",
        ),
    ] = 0,
) -> str:
    user, resource = await _user_resource(resource_id, request)
    
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="`offset` value must be an integer value equal or greater than 0",
        )

    if size <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="`size` value must be an integer value greater than 0",
        )

    if size > OPS_SIZE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"`size` value must be less than {OPS_SIZE_LIMIT} bytes",
        )

    return await router.task_adapter.put_task(
        user, 
        resource, 
        task_models.TaskCommand(
            router=router.get_router_name(),
            command="view",
            args={
                "path": path,
                "size": size or OPS_SIZE_LIMIT,
                "offset": offset or 0,

            }
        )
    )


@router.get(
    "/tail/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Output the last part of a file (`tail`)",
    status_code=status.HTTP_200_OK,
    response_model=str,
    response_description="`tail` operation finished successfully",
)
async def get_tail(
    resource_id: str,
    request : Request,
    path: Annotated[str, Query(description="File path")],
    file_bytes: Annotated[
        int | None,
        Query(
            alias="bytes",
            description="The output will be the last NUM bytes of each file.",
        ),
    ] = None,
    lines: Annotated[
        int | None,
        Query(
            description="The output will be the last NUM lines of each file.",
        ),
    ] = None,
    skip_heading: Annotated[
        bool,
        Query(
            alias="skipHeading",
            description=(
                "The output will be the whole file, without the first NUM "
                "bytes/lines of each file. NUM should be specified in the "
                "respective argument through `bytes` or `lines`."
            ),
        ),
    ] = False,
) -> str:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user, 
        resource, 
        task_models.TaskCommand(
            router=router.get_router_name(),
            command="tail",
            args={
                "path": path,
                "file_bytes": file_bytes,
                "lines": lines,
                "skip_heading": skip_heading,

            }
        )
    )


@router.get(
    "/checksum/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Output the checksum of a file (using SHA-256 algotithm)",
    status_code=status.HTTP_200_OK,
    response_model=str,
    response_description="Checksum returned successfully",
)
async def get_checksum(
    resource_id: str,
    request : Request,
    path: Annotated[str, Query(description="Target system")],
) -> str:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user, 
        resource, 
        task_models.TaskCommand(
            router=router.get_router_name(),
            command="checksum",
            args={
                "path": path,
            }
        )
    )


@router.delete(
    "/rm/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Delete file or directory operation (`rm`)",
    response_description="File or directory deleted successfully",
)
async def delete_rm(
    resource_id: str,
    request : Request,
    path: Annotated[str, Query(description="The path to delete")],
) -> str:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user, 
        resource, 
        task_models.TaskCommand(
            router=router.get_router_name(),
            command="rm",
            args={
                "path": path,
            }
        )
    )


@router.post(
    "/compress/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Compress files and directories using `tar` command",
    status_code=status.HTTP_201_CREATED,
    response_model=str,
    response_description="File and/or directories compressed successfully",
)
async def post_compress(
    resource_id: str,
    request : Request,
    request_model: models.PostCompressRequest,
) -> str:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user, 
        resource, 
        task_models.TaskCommand(
            router=router.get_router_name(),
            command="compress",
            args={
                "request_model": request_model,
            }
        )
    )


@router.post(
    "/extract/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Extract `tar` `gzip` archives",
    status_code=status.HTTP_201_CREATED,
    response_model=str,
    response_description="File extracted successfully",
)
async def post_extract(
    resource_id: str,
    request : Request,
    request_model: models.PostExtractRequest,
) -> str:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user, 
        resource, 
        task_models.TaskCommand(
            router=router.get_router_name(),
            command="extract",
            args={
                "request_model": request_model,
            }
        )
    )


@router.post(
    "/mv/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description=f"Create move file or directory operation (`mv`)",
    status_code=status.HTTP_201_CREATED,
    response_model=models.PostMoveResponse,
    response_description="Move file or directory operation created successfully",
)
async def move_mv(
    resource_id: str,
    request : Request,
    request_model: models.PostMoveRequest,
) -> Any:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user, 
        resource, 
        task_models.TaskCommand(
            router=router.get_router_name(),
            command="mv",
            args={
                "request_model": request_model,
            }
        )
    )


@router.post(
    "/cp/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description=f"Create copy file or directory operation (`cp`)",
    status_code=status.HTTP_201_CREATED,
    response_model=models.PostCopyResponse,
    response_description="Copy file or directory operation created successfully",
)
async def post_cp(
    resource_id: str,
    request : Request,
    request_model: models.PostCopyRequest,
) -> Any:
    user, resource = await _user_resource(resource_id, request)
    return await router.task_adapter.put_task(
        user, 
        resource, 
        task_models.TaskCommand(
            router=router.get_router_name(),
            command="cp",
            args={
                "request_model": request_model,
            }
        )
    )


