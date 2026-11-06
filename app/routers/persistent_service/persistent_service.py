"""Persistent services API router"""

from fastapi import Depends, Header, Request, Response

from ...types.http import forbidExtraQueryParams
from ...types.user import User
from .. import iri_router
from ..error_handlers import DEFAULT_RESPONSES
from ..iri_meta import iri_meta_dict
from . import facility_adapter, models

router = iri_router.IriRouter(
    facility_adapter.FacilityAdapter,
    prefix="/persistent_service",
    tags=["persistent_service"],
)


@router.get(
    "/servers",
    response_model=models.ServerList,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="getPersistentServiceServers",
    openapi_extra=iri_meta_dict("planned"),
)
async def get_servers(
    request: Request,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """Get a list of resources that can be used in this endpoint"""
    return await router.adapter.get_servers(user=user)


@router.get(
    "/servers/{server_id:str}/clusters",
    response_model=models.ClusterList,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="getPersistentServiceClusters",
    openapi_extra=iri_meta_dict("planned"),
)
async def get_clusters(
    server_id: str,
    request: Request,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """Get a list of resources that can be used in this endpoint"""
    return await router.adapter.get_clusters(user=user, server_id=server_id)


@router.get(
    "/servers/{server_id:str}/clusters/{cluster_id:str}/projects",
    response_model=models.ProjectList,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="getPersistentServiceProjects",
    openapi_extra=iri_meta_dict("planned"),
)
async def get_projects(
    server_id: str,
    cluster_id: str,
    request: Request,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """Get a list of resources that can be used in this endpoint"""
    return await router.adapter.get_projects(user=user, server_id=server_id, cluster_id=cluster_id)


@router.post(
    "/servers/{server_id:str}/clusters/{cluster_id:str}/namespaces",
    response_model=models.Namespace,
    response_model_exclude_unset=True,
    responses=DEFAULT_RESPONSES,
    operation_id="createPersistentServiceNamespace",
    openapi_extra=iri_meta_dict("planned"),
)
async def create_namespace(
    server_id: str,
    cluster_id: str,
    namespace_request: models.NamespaceCreateRequest,
    request: Request,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
):
    return await router.adapter.create_namespace(user=user, server_id=server_id, cluster_id=cluster_id, namespace_request=namespace_request)


@router.post(
    "/servers/{server_id:str}/kubeconfig",
    response_class=Response,
    responses={
        **{
            200: {
                "description": "Kubeconfig file",
                "content": {
                    "application/yaml": {"schema": {"type": "string", "format": "binary"}}
                },
            }
        },
        **DEFAULT_RESPONSES,
    },
    operation_id="createPersistentServiceKubeconfig",
    openapi_extra=iri_meta_dict("planned"),
)
async def create_kubeconfig(
    server_id: str,
    kubeconfig_request: models.KubeconfigRequest,
    request: Request,
    user: User = Depends(router.current_user),
    _forbid=Depends(forbidExtraQueryParams()),
):
    kubeconfig = await router.adapter.create_kubeconfig(user=user, server_id=server_id, kubeconfig_request=kubeconfig_request)
    return Response(
        content=kubeconfig,
        media_type="application/yaml",
        headers={
            "Content-Disposition": f'attachment; filename="{server_id}-kubeconfig.yaml"',
            "Cache-Control": "no-store",
        },
    )
