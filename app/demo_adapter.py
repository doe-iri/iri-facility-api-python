from fastapi import Request, HTTPException
import datetime
import random
import uuid
import psij
import time
import os
import stat
import pwd
import grp
import glob
import subprocess
import os
import pathlib
from typing import Any
from .routers.status import models as status_models, facility_adapter as status_adapter
from .routers.account import models as account_models, facility_adapter as account_adapter
from .routers.compute import models as compute_models, facility_adapter as compute_adapter
from .routers.filesystem import models as filesystem_models, facility_adapter as filesystem_adapter


class PathSandbox:
    _base_temp_dir = None
    
    @classmethod
    def get_base_temp_dir(cls):
        if cls._base_temp_dir is None:
            # Create in system temp with a fixed name
            cls._base_temp_dir = os.path.join(
                os.getcwd(), 
                "iri_sandbox"
            )
            os.makedirs(cls._base_temp_dir, exist_ok=True)

            # create a test file
            with open(f"{cls._base_temp_dir}/test.txt", "w") as f:
                f.write("hello world")
        return cls._base_temp_dir
    

class DemoAdapter(status_adapter.FacilityAdapter, account_adapter.FacilityAdapter, compute_adapter.FacilityAdapter, filesystem_adapter.FacilityAdapter):
    def __init__(self):
        self.resources = []
        self.incidents = []
        self.events = []
        self.capabilities = {}
        self.user = account_models.User(id="gtorok", name="Gabor Torok")
        self.projects = []
        self.project_allocations = []
        self.user_allocations = []

        self._init_state()

    
    def _init_state(self):

        day_ago = datetime.datetime.now() - datetime.timedelta(days=1)
        self.capabilities = {
            "cpu": account_models.Capability(id=str(uuid.uuid4()), name="CPU Nodes", units=[account_models.AllocationUnit.node_hours]),
            "gpu": account_models.Capability(id=str(uuid.uuid4()), name="GPU Nodes", units=[account_models.AllocationUnit.node_hours]),
            "hpss": account_models.Capability(id=str(uuid.uuid4()), name="Tape Storage", units=[account_models.AllocationUnit.bytes, account_models.AllocationUnit.inodes]),
            "gpfs": account_models.Capability(id=str(uuid.uuid4()), name="GPFS Storage", units=[account_models.AllocationUnit.bytes, account_models.AllocationUnit.inodes]),
        }

        pm = status_models.Resource(id=str(uuid.uuid4()), group="perlmutter", name="compute nodes", description="the perlmutter computer compute nodes", capability_ids=[
            self.capabilities["cpu"].id,
            self.capabilities["gpu"].id,
        ], current_status=status_models.Status.degraded, last_modified=day_ago, resource_type=status_models.ResourceType.compute)
        hpss = status_models.Resource(id=str(uuid.uuid4()), group="hpss", name="hpss", description="hpss tape storage", capability_ids=[self.capabilities["hpss"].id], current_status=status_models.Status.up, last_modified=day_ago, resource_type=status_models.ResourceType.storage)
        cfs = status_models.Resource(id=str(uuid.uuid4()), group="cfs", name="cfs", description="cfs storage", capability_ids=[self.capabilities["gpfs"].id], current_status=status_models.Status.up, last_modified=day_ago, resource_type=status_models.ResourceType.storage)

        self.resources = [
            pm,
            hpss,
            cfs,
            status_models.Resource(id=str(uuid.uuid4()), group="perlmutter", name="login nodes", description="the perlmutter computer login nodes", capability_ids=[], current_status=status_models.Status.degraded, last_modified=day_ago, resource_type=status_models.ResourceType.system),
            status_models.Resource(id=str(uuid.uuid4()), group="services", name="Iris", description="Iris webapp", capability_ids=[], current_status=status_models.Status.down, last_modified=day_ago, resource_type=status_models.ResourceType.website),
            status_models.Resource(id=str(uuid.uuid4()), group="services", name="sfapi", description="the Superfacility API", capability_ids=[], current_status=status_models.Status.up, last_modified=day_ago, resource_type=status_models.ResourceType.service),
        ]

        self.projects = [
            account_models.Project(
                id=str(uuid.uuid4()),
                name="Staff research project",
                description="Compute and storage allocation for staff research use",
                user_ids=[ "gtorok" ],
            ),
            account_models.Project(
                id=str(uuid.uuid4()),
                name="Test project",
                description="Compute and storage allocation for testing use",
                user_ids=[ "gtorok" ],
            ),
        ]

        for p in self.projects:
            for c in self.capabilities.values():
                pa = account_models.ProjectAllocation(
                    id=str(uuid.uuid4()),
                    project_id=p.id,
                    capability_id=c.id,
                    entries=[
                        account_models.AllocationEntry(
                            allocation=500 + random.random() * 500,
                            usage=100 + random.random() * 100,
                            unit=cu,
                        )
                        for cu in c.units
                    ]
                )
                self.project_allocations.append(pa)
                self.user_allocations.append(
                    account_models.UserAllocation(
                        id=str(uuid.uuid4()),
                        project_id=pa.project_id,
                        project_allocation_id=pa.id,
                        user_id="gtorok",
                        entries=[
                            account_models.AllocationEntry(
                                allocation=a.allocation/10,
                                usage=a.usage/10,
                                unit=a.unit
                            ) 
                            for a in pa.entries
                        ]
                    )
                )

        statuses = { r.name: status_models.Status.up for r in self.resources }        
        last_incidents = {}
        d = datetime.datetime(2025, 3, 1, 10, 0, 0)

        # generate some events and incidents
        # here every incident only has events from a single resource, 
        # but in reality it is possible for an incident to have events from multiple resources
        for i in range(0, 1000):
            r = random.choice(self.resources)
            status = statuses[r.name]
            event = status_models.Event(
                id=str(uuid.uuid4()),
                name=f"{r.name} is {status.value}",
                description=f"{r.name} is {status.value}",
                occurred_at=d,
                status=status,
                resource_id=r.id,
                last_modified=day_ago,
            )
            self.events.append(event)
            if r.name in last_incidents:
                inc = last_incidents[r.name]
                event.incident_id = inc.id
                inc.event_ids.append(event.id)
                if status == status_models.Status.up:
                    inc.end = d
                    del last_incidents[r.name]
            
            if random.random() > 0.9:
                if status == status_models.Status.down:
                    statuses[r.name] = status_models.Status.up
                else:
                    statuses[r.name] = status_models.Status.down
                    dstr = d.strftime("%Y-%m-%d %H:%M:%S.%f%z")
                    incident = status_models.Incident(
                        id=str(uuid.uuid4()), 
                        name=f"{r.name} incident at {dstr}", 
                        description=f"{r.name} incident at {dstr}", 
                        status=status_models.Status.down,
                        event_ids=[],
                        resource_ids=random.choices([r.id for r in self.resources], k=3),
                        start=d,
                        end=d,
                        type=random.choice(list(status_models.IncidentType)),
                        resolution="PM was fixed by NERSC staff",
                        last_modified=d
                    )
                    self.incidents.append(incident)
                    last_incidents[r.name] = incident
                    

            d += datetime.timedelta(minutes=int(random.random() * 15 + 1))


    async def get_resources(
        self : "DemoAdapter",
        offset : int,
        limit : int,
        name : str | None = None,
        description : str | None = None,
        group : str | None = None,
        modified_since : datetime.datetime | None = None,
        resource_type : status_models.ResourceType | None = None,
        ) -> list[status_models.Resource]:
        return status_models.Resource.find(self.resources, name, description, group, modified_since, resource_type)[offset:offset + limit]


    async def get_resource(
        self : "DemoAdapter",
        id : str
        ) -> status_models.Resource:
        return status_models.Resource.find_by_id(self.resources, id)


    async def get_events(
        self : "DemoAdapter",
        incident_id : str,
        offset : int,
        limit : int,
        resource_id : str | None = None,
        name : str | None = None,
        description : str | None = None,
        status : status_models.Status | None = None,
        from_ : datetime.datetime | None = None,
        to : datetime.datetime | None = None,
        time_ : datetime.datetime | None = None,
        modified_since : datetime.datetime | None = None,
        ) -> list[status_models.Event]:        
        return status_models.Event.find([e for e in self.events if e.incident_id == incident_id], resource_id, name, description, status, from_, to, time_, modified_since)[offset:offset + limit]


    async def get_event(
        self : "DemoAdapter",
        incident_id : str,
        id : str
        ) -> status_models.Event:
        return status_models.Event.find_by_id(self.events, id)


    async def get_incidents(
        self : "DemoAdapter",
        offset : int,
        limit : int,
        name : str | None = None,
        description : str | None = None,
        status : status_models.Status | None = None,
        type : status_models.IncidentType | None = None,
        from_ : datetime.datetime | None = None,
        to : datetime.datetime | None = None,
        time_ : datetime.datetime | None = None,
        modified_since : datetime.datetime | None = None,
        resource_id : str | None = None,
        ) -> list[status_models.Incident]:
        return status_models.Incident.find(self.incidents, name, description, status, type, from_, to, time_, modified_since, resource_id)[offset:offset + limit]


    async def get_incident(
        self : "DemoAdapter",
        id : str
        ) -> status_models.Incident:
        return status_models.Incident.find_by_id(self.incidents, id)


    async def get_capabilities(
        self : "DemoAdapter",
        ) -> list[account_models.Capability]:
        return self.capabilities.values()
    

    def get_current_user(
            self : "DemoAdapter",
            request: Request,
            api_key: str
        ) -> str:
        """
            In a real deployment, this would decode the api_key jwt and return the current user's id.
            This method is not async.
        """
        return "gtorok"


    async def get_user(
            self : "DemoAdapter",
            request: Request,
            user_id: str
            ) -> account_models.User:
        return self.user


    async def get_projects(
            self : "DemoAdapter",
            request: Request,
            user: account_models.User
            ) -> list[account_models.Project]:
        return self.projects
    

    async def get_project_allocations(
        self : "DemoAdapter",
        request: Request,
        project: account_models.Project,
        user: account_models.User
        ) -> list[account_models.ProjectAllocation]:
        return [pa for pa in self.project_allocations if pa.project_id == project.id]
    

    async def get_user_allocations(
        self : "DemoAdapter",
        request: Request,
        user: account_models.User,
        project_allocation: account_models.ProjectAllocation,
        ) -> list[account_models.UserAllocation]:
        return [ua for ua in self.user_allocations if ua.project_allocation_id == project_allocation.id]


    async def submit_job(
        self: "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        job: psij.Job,
    ) -> compute_models.Job:
        return compute_models.Job(
            id="job_123",
            status=compute_models.JobStatus(
                state=psij.JobState.NEW,
                time=time.time(),
                message="job submitted",
                exit_code=None,
                meta_data={ "account": "account1" },
            )
        )
    

    async def get_job(
        self: "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        job_id: str,
    ) -> compute_models.Job:
        return compute_models.Job(
            id=job_id,
            status=compute_models.JobStatus(
                state=psij.JobState.COMPLETED,
                time=time.time(),
                message="job completed successfully",
                exit_code=0,
                meta_data={ "account": "account1" },
            )
        )


    async def get_jobs(
        self: "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        offset : int,
        limit : int,
        filters: dict[str, object] | None = None,
    ) -> list[compute_models.Job]:
        return [compute_models.Job(
            id=f"job_{i}",
            status=compute_models.JobStatus(
                state=random.choice([s for s in psij.JobState]),
                time=time.time() - (random.random() * 100),
                message="",
                exit_code=random.choice([0, 0, 0, 0, 0, 1, 1, 128, 127]),
                meta_data={ "account": "account1" },
            )
        ) for i in range(random.randint(3, 10))]
    

    async def cancel_job(
        self: "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        job_id: str,
    ) -> bool:
        # call slurm/etc. to cancel job
        return True
    

    def validate_path(self, path: str, allow_symlinks: bool = True) -> str:
        basedir = PathSandbox.get_base_temp_dir()
        real_path = os.path.realpath(os.path.join(basedir, path))
        
        # Check within sandbox
        if not real_path.startswith(basedir + os.sep) and real_path != basedir:
            raise HTTPException(status_code=400, detail=f"Path outside sandbox: {path}")
        
        # Optionally block symlinks that point outside sandbox
        if not allow_symlinks and os.path.islink(os.path.join(basedir, path)):
            link_target = os.readlink(os.path.join(basedir, path))
            if os.path.isabs(link_target):
                raise HTTPException(status_code=400, detail=f"Absolute symlink not allowed: {path}")
        
        return real_path


    def _file(self, path: str) -> filesystem_models.File:
        # Get file stats (follows symlinks by default)
        rp = self.validate_path(path)
        file_stat = os.stat(rp)  # Use lstat to not follow symlinks
        
        # Get file type
        if stat.S_ISDIR(file_stat.st_mode):
            file_type = "directory"
        elif stat.S_ISLNK(file_stat.st_mode):
            file_type = "symlink"
        elif stat.S_ISREG(file_stat.st_mode):
            file_type = "file"
        else:
            file_type = "other"
        
        # Get link target if it's a symlink
        link_target = None
        if stat.S_ISLNK(file_stat.st_mode):
            link_target = os.readlink(rp)
        
        # Get user and group names
        user = pwd.getpwuid(file_stat.st_uid).pw_name
        group = grp.getgrgid(file_stat.st_gid).gr_name
        
        # Get permissions in rwxrwxrwx format
        permissions = stat.filemode(file_stat.st_mode)
        
        # Get last modified time
        last_modified = datetime.datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        
        # Get size
        size = str(file_stat.st_size)
        
        return filesystem_models.File(
            name=os.path.basename(rp),
            type=file_type,
            link_target=link_target,
            user=user,
            group=group,
            permissions=permissions,
            last_modified=last_modified,
            size=size
        )

    async def chmod(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        request_model: filesystem_models.PutFileChmodRequest
    ) -> filesystem_models.PutFileChmodResponse:
        rp = self.validate_path(request_model.path)
        os.chmod(rp, int(request_model.mode, 8))
        return filesystem_models.PutFileChmodResponse(
            output=self._file(rp)
        )


    async def chown(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        request_model: filesystem_models.PutFileChownRequest
    ) -> filesystem_models.PutFileChownResponse:
        rp = self.validate_path(request_model.path)
        os.chown(rp, request_model.owner, request_model.group)
        return filesystem_models.PutFileChmodResponse(
            output=self._file(rp)
        )


    async def ls(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str, 
        show_hidden: bool, 
        numeric_uid: bool, 
        recursive: bool, 
        dereference: bool,
    ) -> filesystem_models.GetDirectoryLsResponse:
        rp = self.validate_path(path)
        files = glob.glob(rp, recursive=recursive)
        return filesystem_models.GetDirectoryLsResponse(
            output=[self._file(f) for f in files]
        )


    def _headtail(
        self : "DemoAdapter",
        cmd: str,
        path: str, 
        file_bytes: int | None, 
        lines: int | None,             
    ) -> Any:
        args = [cmd]
        if file_bytes:
            args.append("-c")
            args.append(str(file_bytes))
        elif lines:
            args.append("-n")
            args.append(str(lines))
        rp = self.validate_path(path)
        args.append(rp)
        result = subprocess.run(
            args,
            capture_output=True,
            text=True
        )
        content = result.stdout
        return content, -len(content)


    async def head(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str, 
        file_bytes: int | None, 
        lines: int | None, 
        skip_trailing: bool,
    ) -> Any:
        return self._headtail("head", path, file_bytes, lines)


    async def tail(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str, 
        file_bytes: int | None, 
        lines: int | None, 
        skip_trailing: bool,
    ) -> Any:
        return self._headtail("tail", path, file_bytes, lines)


    async def view(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str, 
        size: int,
        offset: int,
    ) -> filesystem_models.GetViewFileResponse:
        rp = self.validate_path(path)
        result = subprocess.run(
            f"tail -n +{offset+1} {rp} | head -n {size}",
            shell=True,
            capture_output=True,
            text=True
        )
        content = result.stdout
        return filesystem_models.GetViewFileResponse(
            output=content,
        )


    async def checksum(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str, 
    ) -> filesystem_models.GetFileChecksumResponse:
        rp = self.validate_path(path)
        result = subprocess.run(
            ["sha256sum", rp],
            capture_output=True,
            text=True
        )
        checksum = result.stdout.split()[0]
        return filesystem_models.GetFileChecksumResponse(
            output=filesystem_models.FileChecksum(
                checksum=checksum,
            )
        )


    async def file(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str, 
    ) -> filesystem_models.GetFileTypeResponse:
        rp = self.validate_path(path)
        result = subprocess.run(
            ["file", "-b", rp],
            capture_output=True,
            text=True
        )
        return filesystem_models.GetFileTypeResponse(
            output=result.stdout.strip(),
        )


    async def stat(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str, 
        dereference: bool,
    ) -> filesystem_models.GetFileStatResponse:
        rp = self.validate_path(path)
        if dereference:
            stat_info = os.stat(rp)
        else:
            stat_info = os.lstat(rp)
        return filesystem_models.GetFileStatResponse(
                output=filesystem_models.FileStat(
                mode=stat_info.st_mode,
                ino=stat_info.st_ino,
                dev=stat_info.st_dev,
                nlink=stat_info.st_nlink,
                uid=stat_info.st_uid,
                gid=stat_info.st_gid,
                size=stat_info.st_size,
                atime=int(stat_info.st_atime),
                ctime=int(stat_info.st_ctime),
                mtime=int(stat_info.st_mtime)
            )
        )


    async def rm(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str, 
    ):
        rp = self.validate_path(path)
        if rp == PathSandbox.get_base_temp_dir():
            raise HTTPException(status_code=400, detail="Cannot delete sandbox")
        subprocess.run(["rm", "-rf", rp], check=True)
        return None


    async def mkdir(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        request_model: filesystem_models.PostMakeDirRequest,
    ) -> filesystem_models.PostMkdirResponse:
        rp = self.validate_path(request_model.path)
        args = ["mkdir"]
        if request_model.parent:
            args.append("-p")
        args.append(rp)
        subprocess.run(args, check=True)
        return filesystem_models.PostMkdirResponse(
            output=self._file(rp)
        )


    async def symlink(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        request_model: filesystem_models.PostFileSymlinkRequest,
    ) -> filesystem_models.PostFileSymlinkResponse:
        rp_src = self.validate_path(request_model.path)
        rp_dst = self.validate_path(request_model.link_path)
        subprocess.run(["ln", "-s", rp_src, rp_dst], check=True)
        return filesystem_models.PostFileSymlinkResponse(
            output=self._file(rp_dst)
        )


    async def download(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str,
    ) -> Any:
        rp = self.validate_path(path)        
        return pathlib.Path(rp).read_bytes()


    async def upload(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        path: str,
        content: str,
    ) -> None:
        rp = self.validate_path(path)
        pathlib.Path(rp).write_bytes(content)


    async def compress(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        request_model: filesystem_models.PostCompressRequest,
    ) -> filesystem_models.PostCompressResponse:
        src_rp = self.validate_path(request_model.path)
        dst_rp = self.validate_path(request_model.target_path)

        args = [ "tar" ]
        if request_model.compression == filesystem_models.CompressionType.gzip:
            args.append("-czf")
        elif request_model.compression == filesystem_models.CompressionType.bzip2:
            args.append("-cjf")
        elif request_model.compression == filesystem_models.CompressionType.xz:
            args.append("-cJf")
        args.append(dst_rp)
        if request_model.dereference:
            args.append("--dereference")
        if request_model.match_pattern:
            args.append(f"--include={request_model.match_pattern}")

        args.append("-C")
        args.append(PathSandbox.get_base_temp_dir())
        p = pathlib.Path(src_rp)
        args.append(p.relative_to(PathSandbox.get_base_temp_dir()))
        subprocess.run(args, check=True)

        return filesystem_models.PostCompressResponse(
            output=self._file(dst_rp)
        )


    async def extract(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        request_model: filesystem_models.PostExtractRequest,
    ) -> filesystem_models.PostExtractResponse:
        src_rp = self.validate_path(request_model.path)
        dst_rp = self.validate_path(request_model.target_path)

        args = [ "tar" ]
        if request_model.compression == filesystem_models.CompressionType.gzip:
            args.append("-xzf")
        elif request_model.compression == filesystem_models.CompressionType.bzip2:
            args.append("-xjf")
        elif request_model.compression == filesystem_models.CompressionType.xz:
            args.append("-xJf")
        else:
            args.append("-xf")
        args.append(src_rp)
        args.append("-C")
        args.append(dst_rp)
        subprocess.run(args, check=True)

        return filesystem_models.PostExtractResponse(
            output=self._file(dst_rp)
        )


    async def mv(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        request_model: filesystem_models.PostMoveRequest,
    ) -> filesystem_models.PostMoveResponse:
        src_rp = self.validate_path(request_model.path)
        dst_rp = self.validate_path(request_model.target_path)
        subprocess.run(["mv", src_rp, dst_rp], check=True)
        return filesystem_models.PostMoveResponse(
            output=self._file(dst_rp)
        )


    async def cp(
        self : "DemoAdapter",
        resource: status_models.Resource, 
        user: account_models.User, 
        request_model: filesystem_models.PostCopyRequest,
    ) -> filesystem_models.PostCopyResponse:
        src_rp = self.validate_path(request_model.path)
        dst_rp = self.validate_path(request_model.target_path)
        args = ["cp"]
        if request_model.dereference:
            args.append("-L")
        args.append(src_rp)
        args.append(dst_rp)
        subprocess.run(args, check=True)
        return filesystem_models.PostCopyResponse(
            output=self._file(dst_rp)
        )
