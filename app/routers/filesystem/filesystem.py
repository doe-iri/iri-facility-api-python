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

def to_int(name, default_value):
    try:
        return os.environ.get(name) or default_value
    except:
        return default_value
    

OPS_SIZE_LIMIT = to_int("OPS_SIZE_LIMIT", 5 * 1024 * 1024)


router = iri_router.IriRouter(
    facility_adapter.FacilityAdapter,
    prefix="/filesystem",
    tags=["filesystem"],
)

async def _user_resource(
        resource_id: str, 
        request: Request,
    ) -> tuple[account_models.User, status_models.Resource]:
    user = await router.adapter.get_user(request.state.current_user_id, request.state.api_key)
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
    response_model=models.PutFileChmodResponse,
    response_description="File permissions changed successfully",
)
async def put_chmod(
    resource_id: str,
    request_model: models.PutFileChmodRequest,
    request : Request,
):
    user, resource = await _user_resource(resource_id, request)
    return await router.adapter.chmod(resource, user, request_model)


@router.put(
    "/chown/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Change the ownership of a given file (`chown`)",
    status_code=status.HTTP_200_OK,
    response_model=models.PutFileChownResponse,
    response_description="File ownership changed successfully",
)
async def put_chown(
    resource_id: str,
    request_model: models.PutFileChownRequest,
    request : Request,
):
    user, resource = await _user_resource(resource_id, request)
    return await router.adapter.chown(resource, user, request_model)


@router.get(
    "/file/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Output the type of a file or directory",
    status_code=status.HTTP_200_OK,
    response_model=models.GetFileTypeResponse,
    response_description="Type returned successfully",
)
async def get_file(
    resource_id: str,
    request : Request,
    path: Annotated[str, Query(description="A file or folder path")],
) -> Any:
    user, resource = await _user_resource(resource_id, request)
    return await router.adapter.file(resource, user, path)


@router.get(
    "/stat/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Output the `stat` of a file",
    status_code=status.HTTP_200_OK,
    response_model=models.GetFileStatResponse,
    response_description="Stat returned successfully",
)
async def get_stat(
    resource_id: str,
    request : Request,
    path: Annotated[str, Query(description="A file or folder path")],
    dereference: Annotated[bool, Query(description="Follow symbolic links")] = False,
) -> Any:
    user, resource = await _user_resource(resource_id, request)
    return await router.adapter.stat(resource, user, path, dereference)


@router.post(
    "/mkdir/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Create directory operation (`mkdir`)",
    status_code=status.HTTP_201_CREATED,
    response_model=models.PostMkdirResponse,
    response_description="Directory created successfully",
)
async def post_mkdir(
    resource_id: str,
    request : Request,
    request_model: models.PostMakeDirRequest,
) -> Any:
    user, resource = await _user_resource(resource_id, request)
    return await router.adapter.mkdir(resource, user, request_model)



@router.post(
    "/symlink/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Create symlink operation (`ln`)",
    status_code=status.HTTP_201_CREATED,
    response_model=models.PostFileSymlinkResponse,
    response_description="Symlink created successfully",
)
async def post_symlink(
    resource_id: str,
    request : Request,
    request_model: models.PostFileSymlinkRequest,
) -> Any:
    user, resource = await _user_resource(resource_id, request)
    return await router.adapter.symlink(resource, user, request_model)
