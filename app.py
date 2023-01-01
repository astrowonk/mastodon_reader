import dash_bootstrap_components as dbc

from dash import Dash, dcc, html
from dash.dependencies import Input, Output, State
from mastodon import Mastodon
from flask import request
from dash.exceptions import PreventUpdate
from urllib.parse import parse_qs
from encryption import encode, decode
import datetime
from fave_articles import make_card, get_processed_data

from pathlib import Path

parent_dir = Path().absolute().stem
url_base_path_name = f"/dash/{parent_dir}/"

STYLE = {"marginBottom": 20, "marginTop": 20, 'width': '85%'}
STYLE_BANNER = {
    "marginBottom": 20,
    "marginTop": 20,
    'width': '85%',
    'margin-left': 'auto',
    'margin-right': 'auto',
}

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.COSMO, dbc.icons.BOOTSTRAP],
    url_base_pathname=url_base_path_name,
    title="Mastodon Link List",
)

button_class = 'me-1'

app.layout = dbc.Container([
    dbc.Button("Authorize Instance", id='button', class_name=button_class),
    # dbc.Button("Visit Instance", id="redirect-button"),
    dcc.Input(id='instance-name',
              persistence=True,
              persistence_type='local',
              placeholder='Mastodon instance, e.g. mastodon.social',
              style={'width': '80%'}),
    html.Div(id='authorize-div'),
    html.H3(
        "Links from Mastodon Favorites and Bookmarks",
        style=STYLE_BANNER,
    ),
    dbc.Spinner(html.Div(id='output')),
    dcc.Location(id='location', refresh=True),
    dcc.Store(id='auth-code', storage_type='local'),
    dcc.Store(id='tokens', storage_type='local'),
    dcc.Store(id='access-token', storage_type='local'),
    dcc.Store(id='article-cache', storage_type='local'),
])


@app.callback(Output('auth-code', 'data'), Input('location', 'search'),
              State('tokens', 'data'), State('auth-code', 'data'),
              State('access-token', 'data'))
def parse_access_code(search, tokens, auth_code, access_token):
    """When bouncing back from the instance with the code in the URL, pull out the code and store it."""
    if access_token:
        raise PreventUpdate
    if not search or not search.startswith(
            '?code') or not tokens or not tokens.get(
                'instance_name') or auth_code:
        raise PreventUpdate
    code = parse_qs(search[1:])['code'][0]
    return {'code': encode(code)}


@app.callback(Output('tokens', 'data'),
              Input('button', 'n_clicks'),
              State('instance-name', 'value'),
              prevent_initial_call=True)
def get_token(_, instance_name):
    """Gets the client secrets and ids needed to start the whole oath dance."""
    if not instance_name:
        raise PreventUpdate
    redirect_uri = request.host_url + url_base_path_name[1:] + 'auth'
    print(redirect_uri)
    client_id, client_secret = Mastodon.create_app(
        'mastodon-link-reader',
        scopes=['read'],
        redirect_uris=redirect_uri,
        api_base_url=f'https://{instance_name}')

    tokens = {'client_secret': client_secret, 'client_id': client_id}
    return {
        'client_secret': encode(client_secret),
        'client_id': encode(client_id),
        'instance_name': instance_name
    }


@app.callback(Output('location', 'href'),
              State('location', 'href'),
              Input('tokens', 'modified_timestamp'),
              State('tokens', 'data'),
              State('instance-name', 'value'),
              State('auth-code', 'data'),
              State('access-token', 'data'),
              prevent_initial_call=True)
def update_location(location, ts, data, instance_name, auth_code,
                    access_token):
    """Creates and redirects to the authentication url of the mastodon instance"""
    if ('auth' in
            location  #have to check for auth in the url otherwise because this callback fires 
            #at the same time as the auth_token getting set and the other conditionals won't be met
        ) or access_token or auth_code or not data or not instance_name:
        raise PreventUpdate

    m = Mastodon(client_id=decode(data['client_id']),
                 client_secret=decode(data['client_secret']),
                 api_base_url=f'https://{instance_name}')

    redirect_uri = request.host_url + url_base_path_name[1:] + 'auth'

    url = m.auth_request_url(redirect_uris=redirect_uri, scopes=['read'])
    return url


@app.callback(Output('access-token', 'data'), Input('auth-code', 'data'),
              State('tokens', 'data'), State('access-token', 'data'))
def update_final_token(data, tokens, access_token):
    """Gets the actual useful access token after the code is stored and set from the redirect."""
    if not data or access_token:
        raise PreventUpdate
    api_base_url = f"https://{tokens['instance_name']}"
    redirect_uri = request.host_url + url_base_path_name[1:] + 'auth'

    m = Mastodon(api_base_url=api_base_url,
                 client_id=decode(tokens['client_id']),
                 client_secret=decode(tokens['client_secret']))
    token = m.log_in("marcoshuerta@vmst.io",
                     code=decode(data['code']),
                     redirect_uri=redirect_uri,
                     scopes=['read'])
    return ({'access_token': encode(token)})


@app.callback(Output('article-cache', 'data'), Input('access-token', 'data'),
              State('tokens', 'data'),
              State('article-cache', 'modified_timestamp'),
              State('article-cache', 'data'))
def update_data(access_token, tokens, ts, cached_data):
    """Loads data from the mastodon api into local storage using the access token"""
    if not access_token:
        raise PreventUpdate
    if ts != -1:
        ts = datetime.datetime.fromtimestamp(ts / 1000.0)
    if (ts != -1
        ) and datetime.datetime.now() < (ts + datetime.timedelta(minutes=5)):
        print("Using cached data, not loading."
              )  # need to add a manual refresh button
        raise PreventUpdate
    if cached_data:
        max_favorite_id, max_bookmark_id = cached_data.get(
            'fave_id_pagination'), cached_data.get('bookmark_id_pagination')
    else:
        max_favorite_id, max_bookmark_id = None, None

    api_base_url = f"https://{tokens['instance_name']}"
    m = Mastodon(api_base_url=api_base_url,
                 client_id=tokens['client_id'],
                 client_secret=tokens['client_secret'],
                 access_token=decode(access_token['access_token']))
    mydata = get_processed_data(m,
                                min_fave_id=max_favorite_id,
                                min_bookmark_id=max_bookmark_id)

    if cached_data:
        mydata['posts'] = mydata['posts'] + cached_data['posts']
    print("max ids")
    print(max_favorite_id, max_bookmark_id)
    print()
    return mydata


@app.callback(Output('output', 'children'), Input('article-cache', 'data'),
              State('tokens', 'data'))
def update_output(mydata, tokens):
    """Gets the data from local storage and actually makes the web site"""
    if not mydata:
        raise PreventUpdate

    api_base_url = f"https://{tokens['instance_name']}"

    return dbc.Container([
        dbc.Row([dbc.Col(make_card(x, api_base_url))]) for x in mydata['posts']
    ],
                         style=STYLE)


if __name__ == "__main__":
    app.run_server(debug=True)