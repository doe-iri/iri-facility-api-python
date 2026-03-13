"""
This script manages the resource server for the data movement API. It allows you to view, create, and delete scopes
for the resource server.

It's only useful to admins of the data movement API.
"""

import typer
import globus_sdk
import pprint
import os

GLOBUS_RS_ID = os.environ.get("GLOBUS_RS_ID")
GLOBUS_RS_SECRET = os.environ.get("GLOBUS_RS_SECRET")
GLOBUS_RS_SCOPE_SUFFIX = os.environ.get("GLOBUS_RS_SCOPE_SUFFIX")
GLOBUS_SCOPE = f"https://auth.globus.org/scopes/{GLOBUS_RS_ID}/{GLOBUS_RS_SCOPE_SUFFIX}"

global client
app = typer.Typer(no_args_is_help=True)


@app.command()
def client_show():
    print(client.get_client(client_id=GLOBUS_RS_ID))


@app.command()
def scopes_show():
    scope_ids = client.get_client(client_id=GLOBUS_RS_ID)["client"]["scopes"]
    scopes = [client.get_scope(scope_id).data for scope_id in scope_ids]
    pprint.pprint(scopes)


@app.command()
def scope_show(scope: str = None, scope_string: str = None):
    if not scope and not scope_string:
        scope_string = GLOBUS_SCOPE
    if scope_string:
        print(client.get_scopes(scope_strings=[scope_string]))
    else:
        print(client.get_scope(scope_id=scope))


@app.command()
def scope_create_iri():
    if typer.confirm("Create a new IRI API scope?"):
        print(
            client.create_scope(
                GLOBUS_RS_ID,
                "IRI API",
                "Access to IRI API services",
                "iri_api",
                advertised=True,
                allows_refresh_token=True,
            )
        )


@app.command()
def scope_delete(scope: str):
    print(client.delete_scope(scope_id=scope))


if __name__ == "__main__":
    if not GLOBUS_RS_SECRET:
        print("Error: No CLIENT_SECRET detected on env. Please set 'export CLIENT_SECRET=your_secret'")
    else:
        globus_app = globus_sdk.ClientApp("manage-ap", client_id=GLOBUS_RS_ID, client_secret=GLOBUS_RS_SECRET)
        client = globus_sdk.AuthClient(app=globus_app)
        client.add_app_scope(globus_sdk.AuthClient.scopes.manage_projects)
        app()
