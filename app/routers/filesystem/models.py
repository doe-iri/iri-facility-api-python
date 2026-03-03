"""Filesystem-related models."""
# Copied from: https://github.com/eth-cscs/firecrest-v2/blob/master/src/firecrest/filesystem/ops/models.py
#
# Copyright (c) 2025, ETH Zurich. All rights reserved.
#
# Please, refer to the LICENSE file in the root directory.
# SPDX-License-Identifier: BSD-3-Clause

from enum import Enum
from pydantic import Field, AliasChoices, BaseModel


class CompressionType(str, Enum):
    """Defines the type of compression to be used for compressing or extracting files."""
    none = "none"
    bzip2 = "bzip2"
    gzip = "gzip"
    xz = "xz"


class ContentUnit(str, Enum):
    """Defines the unit of content for file operations."""
    lines = "lines"
    bytes = "bytes"


class File(BaseModel):
    """Represents a file or directory in the filesystem."""
    name: str = Field(..., description="File name", example="file.txt")
    type: str = Field(..., description="File type", example="file")
    link_target: str|None = Field(default=None, description="Target path if the file is a symbolic link", example="/data/file.txt")
    user: str = Field(..., description="Owner username", example="user")
    group: str = Field(..., description="Owner group", example="users")
    permissions: str = Field(..., description="POSIX permission string", example="rwxr-xr-x")
    last_modified: str = Field(..., description="Last modification timestamp", example="2026-02-21T12:00:00Z")
    size: str = Field(..., description="File size in bytes as string", example="1024")


class FileContent(BaseModel):
    """Represents the content of a file, along with metadata about the content."""
    content: str = Field(..., description="File content segment", example="Hello world")
    content_type: ContentUnit = Field(..., description="Unit used for content slicing", example="lines")
    start_position: int = Field(..., description="Start position of the returned content", example=0)
    end_position: int = Field(..., description="End position of the returned content", example=10)


class FileChecksum(BaseModel):
    """Represents the checksum information of a file."""
    algorithm: str = Field(default="SHA-256", description="Checksum algorithm", example="SHA-256")
    checksum: str = Field(..., description="Checksum value", example="3a7bd3e2360a3d...")


class FileStat(BaseModel):
    """Represents the metadata information of a file."""
    # message: str
    mode: int = Field(..., description="File mode", example=33188)
    ino: int = Field(..., description="Inode number", example=123456)
    dev: int = Field(..., description="Device ID", example=2049)
    nlink: int = Field(..., description="Number of hard links", example=1)
    uid: int = Field(..., description="User ID of owner", example=1000)
    gid: int = Field(..., description="Group ID of owner", example=1000)
    size: int = Field(..., description="File size in bytes", example=1024)
    atime: int = Field(..., description="Last access time (epoch seconds)", example=1708531200)
    ctime: int = Field(..., description="Last metadata change time (epoch seconds)", example=1708531200)
    mtime: int = Field(..., description="Last modification time (epoch seconds)", example=1708531200)
    # birthtime: int


class PatchFile(BaseModel):
    """Represents the result of a file patch operation."""
    message: str = Field(..., description="Result message", example="File updated")
    new_filepath: str = Field(..., description="New file path", example="/home/user/file.new")
    new_permissions: str = Field(..., description="Updated permissions", example="755")
    new_owner: str = Field(..., description="Updated owner", example="user")


class PatchFileMetadataRequest(BaseModel):
    """Represents a request to update file metadata."""
    new_filename: str|None = Field(default=None, description="New file name", example="file.new")
    new_permissions: str|None = Field(default=None, description="New permissions", example="755")
    new_owner: str|None = Field(default=None, description="New owner", example="user")


class GetDirectoryLsResponse(BaseModel):
    """Represents the response for a directory listing."""
    output: list[File]|None = Field(default=None, description="Directory listing")


class GetFileHeadResponse(BaseModel):
    """Represents the response for reading the beginning of a file."""
    output: FileContent|None = Field(default=None, description="File content from the beginning")


class GetFileTailResponse(BaseModel):
    """Represents the response for reading the end of a file."""
    output: FileContent|None = Field(default=None, description="File content from the end")


class GetFileChecksumResponse(BaseModel):
    """Represents the response for getting file checksum information."""
    output: FileChecksum|None = Field(default=None, description="File checksum information")


class GetFileTypeResponse(BaseModel):
    """Represents the response for getting the type of a file."""
    output: str|None = Field(default=None, description="Type of the file", example="directory")


class GetFileStatResponse(BaseModel):
    """Represents the response for getting file metadata information."""
    output: FileStat|None = Field(default=None, description="File stat information")


class GetFileDownloadResponse(BaseModel):
    """Represents the response for downloading a file."""
    output: str|None = Field(default=None, description="Download URL or identifier", example="https://example.com/download/file")


class PatchFileMetadataResponse(BaseModel):
    """Represents the response for updating file metadata."""
    output: PatchFile|None = Field(default=None, description="Updated file metadata")


class FilesystemRequestBase(BaseModel):
    """Base class for filesystem operation requests."""
    # Should we allow both: path and source_path? Or just one of them?
    path: str|None = Field(default=None, validation_alias=AliasChoices("path", "source_path"), description="Source file or directory path", example="/home/user/dir")


class PutFileChmodRequest(FilesystemRequestBase):
    """Represents a request to change file permissions."""
    mode: str = Field(..., description="Mode in octal permission format", example="777")
    model_config = {"json_schema_extra": {"examples": [{"path": "/home/user/dir/file.out", "mode": "777"}]}}


class PutFileChmodResponse(BaseModel):
    """Represents the response for changing file permissions."""
    output: File|None = Field(default=None, description="Updated file metadata")


class PutFileChownRequest(FilesystemRequestBase):
    """Represents a request to change file ownership."""
    owner: str = Field(default="", description="User name of the new user owner of the file", example="user")
    group: str = Field(default="", description="Group name of the new group owner of the file", example="my-group")
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
    """Represents the response for changing file ownership."""
    output: File|None = Field(default=None, description="Updated file metadata")


class PutFileUploadResponse(BaseModel):
    """Represents the response for uploading a file."""
    output: str|None = Field(default=None, description="Upload result or identifier")


class PostMakeDirRequest(FilesystemRequestBase):
    """Represents a request to create a directory."""
    parent: bool = Field(default=False, description="If set to `true` creates all its parent directories if they do not already exist", example=True)
    model_config = {"json_schema_extra": {"examples": [{"path": "/home/user/dir/newdir", "parent": "true"}]}}


class PostFileSymlinkRequest(FilesystemRequestBase):
    """Represents a request to create a symbolic link."""
    link_path: str = Field(..., description="Path to the new symlink", example="/home/user/newlink")
    model_config = {"json_schema_extra": {"examples": [{"path": "/home/user/dir", "link_path": "/home/user/newlink"}]}}


class PostFileSymlinkResponse(BaseModel):
    """Represents the response for creating a symbolic link."""
    output: File|None = Field(default=None, description="Created symlink metadata")


class GetViewFileResponse(BaseModel):
    """Represents the response for viewing a file."""
    output: FileContent|None = Field(default=None, description="File content")


class PostMkdirResponse(BaseModel):
    """Represents the response for creating a directory."""
    output: File|None = Field(default=None, description="Created directory metadata")


class PostCompressResponse(BaseModel):
    """Represents the response for compressing a file."""
    output: File|None = Field(default=None, description="Compressed file metadata")


class PostCompressRequest(FilesystemRequestBase):
    """Represents a request to compress a file."""
    target_path: str = Field(..., description="Path to the compressed file", example="/home/user/file.tar.gz")
    match_pattern: str|None = Field(default=None, description="Regex pattern to filter files to compress", example=".*\\.txt$")
    dereference: bool = Field(default=False, description="If set to `true`, it follows symbolic links and archive the files they point to instead of the links themselves.", example=True)
    compression: CompressionType = Field(default="gzip", description="Defines the type of compression to be used. By default gzip is used.", example="gzip")
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
    """Represents the response for extracting a compressed file."""
    output: File|None = Field(default=None, description="Extracted file metadata")


class PostExtractRequest(FilesystemRequestBase):
    """Represents a request to extract a compressed file."""
    target_path: str = Field(..., description="Path to the directory where to extract the compressed file", example="/home/user/dir")
    compression: CompressionType = Field(default="gzip", description="Defines the type of compression to be used. By default gzip is used.", example="gzip")
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
    """Represents a request to copy a file."""
    target_path: str = Field(..., description="Target path of the copy operation", example="/home/user/dir/file.new")
    dereference: bool = Field(default=False, description=("If set to `true`, it follows symbolic links and copies the files they point to instead of the links themselves."), example=True)
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
    """Represents the response for copying a file."""
    output: File|None = Field(default=None, description="Copied file metadata")


class PostMoveRequest(FilesystemRequestBase):
    """Represents a request to move a file."""
    target_path: str = Field(..., description="Target path of the move operation", example="/home/user/dir/file.new")
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
    """Represents the response for moving a file."""
    output: File|None = Field(default=None, description="Moved file metadata")


class RemoveResponse(BaseModel):
    """Represents the response for removing a file or directory."""
    output: str|None = Field(default=None, description="Removal result message")
