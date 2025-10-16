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
    user = await router.adapter.get_user(request, request.state.current_user_id)
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
    "/ls/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="List the contents of the given directory (`ls`)",
    status_code=status.HTTP_200_OK,
    response_model=models.GetDirectoryLsResponse,
    response_description="Directory listed successfully",
)
async def get_ls(
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
) -> Any:
    user, resource = await _user_resource(resource_id, request)
    return await router.adapter.ls(resource, user, path, show_hidden, numeric_uid, recursive, dereference)


@router.get(
    "/head/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Output the first part of file/s (`head`)",
    status_code=status.HTTP_200_OK,
    response_model=models.GetFileHeadResponse,
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
) -> Any:
    user, resource = await _user_resource(resource_id, request)
    output, end_position = await router.adapter.head(resource, user, path, file_bytes, lines, skip_trailing)

    return {
        "output": {
            "content": output,
            "contentType": "bytes" if file_bytes else "lines",
            "startPosition": 0,
            "endPosition": end_position,
        }
    }


@router.get(
    "/view/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description=f"View file content (up to max {OPS_SIZE_LIMIT} bytes)",
    status_code=status.HTTP_200_OK,
    response_model=models.GetViewFileResponse,
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
) -> Any:
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

    return await router.adapter.view(resource, user, path, size or OPS_SIZE_LIMIT, offset or 0)


@router.get(
    "/tail/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Output the last part of a file (`tail`)",
    status_code=status.HTTP_200_OK,
    response_model=models.GetFileTailResponse,
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
) -> Any:
    user, resource = await _user_resource(resource_id, request)
    output, start_position = await router.adapter.tail(resource, user, path, file_bytes, lines, skip_heading)
    return {
        "output": {
            "content": output,
            "contentType": "bytes" if file_bytes else "lines",
            "startPosition": start_position,
            "endPosition": -1,
        }
    }


@router.get(
    "/checksum/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Output the checksum of a file (using SHA-256 algotithm)",
    status_code=status.HTTP_200_OK,
    response_model=models.GetFileChecksumResponse,
    response_description="Checksum returned successfully",
)
async def get_checksum(
    resource_id: str,
    request : Request,
    path: Annotated[str, Query(description="Target system")],
) -> Any:
    user, resource = await _user_resource(resource_id, request)
    return await router.adapter.checksum(resource, user, path)


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


@router.delete(
    "/rm/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Delete file or directory operation (`rm`)",
    status_code=status.HTTP_204_NO_CONTENT,
    response_description="File or directory deleted successfully",
)
async def delete_rm(
    resource_id: str,
    request : Request,
    path: Annotated[str, Query(description="The path to delete")],
) -> None:
    user, resource = await _user_resource(resource_id, request)
    await router.adapter.rm(resource, user, path)
    return None


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


@router.get(
    "/download/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description=f"Download a small file (max {OPS_SIZE_LIMIT} Bytes)",
    status_code=status.HTTP_200_OK,
    response_model=None,
    response_description="File downloaded successfully",
)
async def get_download(
    resource_id: str,
    request : Request,
    path: Annotated[str, Query(description="A file to download")],
) -> Any:
    user, resource = await _user_resource(resource_id, request)
    output = await router.adapter.download(resource, user, path)

    if len(output) > OPS_SIZE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File to download is too large.",
        )

    return Response(
        content=output, media_type="application/octet-stream"
    )


@router.post(
    "/upload/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description=f"Upload a small file (max {OPS_SIZE_LIMIT} Bytes)",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_description="File uploaded successfully",
)
async def post_upload(
    resource_id: str,
    request : Request,
    path: Annotated[
        str, Query(description="Specify path where file should be uploaded.")
    ],
    file: UploadFile = File(description="File to be uploaded as `multipart/form-data`"),
) -> Any:
    user, resource = await _user_resource(resource_id, request)
    raw_content = file.file.read()

    if len(raw_content) > OPS_SIZE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File to upload is too large.",
        )
    await router.adapter.upload(resource, user, path, raw_content)
    return None


@router.post(
    "/compress/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Compress files and directories using `tar` command",
    status_code=status.HTTP_201_CREATED,
    response_model=models.PostCompressResponse,
    response_description="File and/or directories compressed successfully",
)
async def post_compress(
    resource_id: str,
    request : Request,
    request_model: models.PostCompressRequest,
) -> Any:
    user, resource = await _user_resource(resource_id, request)
    return await router.adapter.compress(resource, user, request_model)


@router.post(
    "/extract/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description="Extract `tar` `gzip` archives",
    status_code=status.HTTP_201_CREATED,
    response_model=models.PostExtractResponse,
    response_description="File extracted successfully",
)
async def post_extract(
    resource_id: str,
    request : Request,
    request_model: models.PostExtractRequest,
) -> Any:
    user, resource = await _user_resource(resource_id, request)
    return await router.adapter.extract(resource, user, request_model)


@router.post(
    "/mv/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description=f"Create move file or directory operation (`mv`) (for files larger than {OPS_SIZE_LIMIT} Bytes)",
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
    return await router.adapter.mv(resource, user, request_model)


@router.post(
    "/cp/{resource_id:str}",
    dependencies=[Depends(router.current_user)],
    description=f"Create copy file or directory operation (`cp`) (for files larger than {OPS_SIZE_LIMIT} Bytes)",
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
    return await router.adapter.cp(resource, user, request_model)
