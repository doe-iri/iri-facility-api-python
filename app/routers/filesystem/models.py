# Copied from: https://github.com/eth-cscs/firecrest-v2/blob/master/src/firecrest/filesystem/ops/models.py
#
# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from enum import Enum
from typing import Optional
from pydantic import Field, AliasChoices, BaseModel


class CompressionType(str, Enum):
    none = "none"
    bzip2 = "bzip2"
    gzip = "gzip"
    xz = "xz"


class ContentUnit(str, Enum):
    lines = "lines"
    bytes = "bytes"


class File(BaseModel):
    name: str
    type: str
    link_target: Optional[str]
    user: str
    group: str
    permissions: str
    last_modified: str
    size: str


class FileContent(BaseModel):
    content: str
    content_type: ContentUnit
    start_position: int
    end_position: int


class FileChecksum(BaseModel):
    algorithm: str = "SHA-256"
    checksum: str


class FileStat(BaseModel):
    # message: str
    mode: int
    ino: int
    dev: int
    nlink: int
    uid: int
    gid: int
    size: int
    atime: int
    ctime: int
    mtime: int
    # birthtime: int


class PatchFile(BaseModel):
    message: str
    new_filepath: str
    new_permissions: str
    new_owner: str


class PatchFileMetadataRequest(BaseModel):
    new_filename: Optional[str] = None
    new_permissions: Optional[str] = None
    new_owner: Optional[str] = None


class GetDirectoryLsResponse(BaseModel):
    output: Optional[list[File]]


class GetFileHeadResponse(BaseModel):
    output: Optional[FileContent]
    offset: Optional[int] = Field(default=0, description="Offset in bytes from the beginning of the file where to start reading the content")


class GetFileTailResponse(BaseModel):
    output: Optional[FileContent]
    offset: Optional[int] = Field(default=0, description="Offset in bytes from the beginning of the file where to start reading the content")


class GetFileChecksumResponse(BaseModel):
    output: Optional[FileChecksum]


class GetFileTypeResponse(BaseModel):
    output: Optional[str] = Field(example="directory")


class GetFileStatResponse(BaseModel):
    output: Optional[FileStat]


class GetFileDownloadResponse(BaseModel):
    output: Optional[str]

class PatchFileMetadataResponse(BaseModel):
    output: Optional[PatchFile]


class FilesystemRequestBase(BaseModel):
    # Should we allow both: path and source_path? Or just one of them?
    path: Optional[str] = Field(validation_alias=AliasChoices("path", "source_path"), example="/home/user/dir")


class PutFileChmodRequest(FilesystemRequestBase):
    mode: str = Field(..., description="Mode in octal permission format")
    model_config = {"json_schema_extra": {"examples": [{"path": "/home/user/dir/file.out", "mode": "777"}]}}


class PutFileChmodResponse(BaseModel):
    output: Optional[File]


class PutFileChownRequest(FilesystemRequestBase):
    owner: Optional[str] = Field(default="", description="User name of the new user owner of the file")
    group: Optional[str] = Field(default="", description="Group name of the new group owner of the file")
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "path": "/home/user/dir/file.out",
                    "owner": "user",
                    "group": "my-group",
                }
            ]
        }
    }


class PutFileChownResponse(BaseModel):
    output: Optional[File]

class PutFileUploadResponse(BaseModel):
    output: Optional[str]

class PostMakeDirRequest(FilesystemRequestBase):
    parent: Optional[bool] = Field(
        default=False,
        description="If set to `true` creates all its parent directories if they do not already exist",
    )
    model_config = {"json_schema_extra": {"examples": [{"path": "/home/user/dir/newdir", "parent": "true"}]}}


class PostFileSymlinkRequest(FilesystemRequestBase):
    link_path: str = Field(description="Path to the new symlink")
    model_config = {"json_schema_extra": {"examples": [{"path": "/home/user/dir", "link_path": "/home/user/newlink"}]}}


class PostFileSymlinkResponse(BaseModel):
    output: Optional[File]


class GetViewFileResponse(BaseModel):
    output: Optional[str]


class PostMkdirResponse(BaseModel):
    output: Optional[File]


class PostCompressResponse(BaseModel):
    output: Optional[File]


class PostCompressRequest(FilesystemRequestBase):
    target_path: str = Field(description="Path to the compressed file")
    match_pattern: Optional[str] = Field(default=None, description="Regex pattern to filter files to compress")
    dereference: Optional[bool] = Field(
        default=False,
        description="If set to `true`, it follows symbolic links and archive the files they point to instead of the links themselves.",
    )
    compression: Optional[CompressionType] = Field(
        default="gzip",
        description="Defines the type of compression to be used. By default gzip is used.",
    )
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source_path": "/home/user/dir",
                    "target_path": "/home/user/file.tar.gz",
                    "match_pattern": "*./[ab].*\\.txt",
                    "dereference": "true",
                    "compression": "none",
                }
            ]
        }
    }


class PostExtractResponse(BaseModel):
    output: Optional[File]


class PostExtractRequest(FilesystemRequestBase):
    target_path: str = Field(description="Path to the directory where to extract the compressed file")
    compression: Optional[CompressionType] = Field(
        default="gzip",
        description="Defines the type of compression to be used. By default gzip is used.",
    )
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source_path": "/home/user/dir/file.tar.gz",
                    "target_path": "/home/user/dir",
                    "compression": "none",
                }
            ]
        }
    }


class PostCopyRequest(FilesystemRequestBase):
    target_path: str = Field(description="Target path of the copy operation")
    dereference: Optional[bool] = Field(
        default=False,
        description=("If set to `true`, it follows symbolic links and copies the files they point to instead of the links themselves."),
    )
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source_path": "/home/user/dir/file.orig",
                    "target_path": "/home/user/dir/file.new",
                    "dereference": "true",
                }
            ]
        }
    }


class PostCopyResponse(BaseModel):
    output: Optional[File]


class PostMoveRequest(FilesystemRequestBase):
    target_path: str = Field(description="Target path of the move operation")
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source_path": "/home/user/dir/file.orig",
                    "target_path": "/home/user/dir/file.new",
                }
            ]
        }
    }


class PostMoveResponse(BaseModel):
    output: Optional[File]

class RemoveResponse(BaseModel):
    output: Optional[str]