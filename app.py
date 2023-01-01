import dash_bootstrap_components as dbc

from dash import Dash, dcc, html, callback_context
from dash.dependencies import Input, Output, State
from mastodon import Mastodon
from flask import request
from dash.exceptions import PreventUpdate
from urllib.parse import parse_qs
from encryption import encode, decode
import datetime
from fave_articles import make_card, get_processed_data
from time import sleep

from pathlib import Path

parent_dir = Path().absolute().stem
url_base_path_name = f"/dash/{parent_dir}/"

STYLE = {"marginBottom": 20, "marginTop": 20, 'width': '85%'}
STYLE_BANNER = {
    "marginBottom": 20,
    "marginTop": 20,
    'width': '85%',
    'display': 'inline-block',
    'text-align': 'center',
}

app = Dash(__name__,
           external_stylesheets=[dbc.themes.COSMO, dbc.icons.BOOTSTRAP],
           url_base_pathname=url_base_path_name,
           title="Mastodon Link List",
           suppress_callback_exceptions=True)
server = app.server
button_class = 'me-1'

app.layout = dbc.Container([
    dbc.Spinner(html.Div(id='fs-spinner', style={'margin': 'auto'})),
    html.Div(id='authorization-div', hidden=False),
    dbc.Spinner(html.Div(id='output')),
    dcc.Location(id='location', refresh=False),
    dcc.Store(id='auth-code', storage_type='local'),
    dcc.Store(id='tokens', storage_type='local'),
    dcc.Store(id='access-token', storage_type='local'),
    dcc.Store(id='article-cache', storage_type='local'),
])


@app.callback(Output('authorization-div', 'children'),
              Input('output', 'children'), State('access-token', 'data'))
def make_authorization_ui(loc, data):
    if not data:
        return [
            html.H3(
                "Links from Mastodon Favorites and Bookmarks",
                style=STYLE_BANNER,
            ),
            dbc.InputGroup(
                [
                    dbc.InputGroupText(
                        html.I(className="bi bi-mastodon",
                               style={'float': 'right'})),
                    dbc.Input(
                        id='instance-name',
                        persistence=True,
                        persistence_type='local',
                        placeholder='Mastodon instance, e.g. mastodon.social',
                        style={'width': '80%'}),
                    dbc.Button("Authorize",
                               id='authorize-button',
                               class_name=button_class),
                    html.Div(dbc.Button("Logout", id='logout-button'),
                             hidden=True)  #fake logout button for 
                ],
                style={
                    'width': '80%',
                    'margin': 'auto'
                })
        ]
    return [
        html.H3(
            "Links from Mastodon Favorites and Bookmarks",
            style=STYLE_BANNER,
        ),
        dbc.Button("Logout",
                   id='logout-button',
                   class_name=button_class,
                   style={
                       'float': 'right',
                       'display': 'inline-block',
                       'margin-top': 20
                   }),
        html.Div(
            [
                dbc.Button("", id='authorize-button'),
                dbc.Input(
                    id='instance-name',
                    persistence=True,
                    persistence_type='local',
                ),
            ],
            hidden=True)  #fake objects to avoid nonexistent object complaints
    ]


@app.callback([
    Output('tokens', 'data'),
    Output('auth-code', 'clear_data'),
    Output('access-token', 'clear_data'),
    Output('article-cache', 'clear_data')
],
              Input('authorize-button', 'n_clicks'),
              Input('logout-button', 'n_clicks'),
              State('instance-name', 'value'),
              prevent_initial_call=True)
def get_token(click_authorize, click_logout, instance_name):
    """Gets the client secrets and ids needed to start the whole oath dance."""

    if not (click_authorize or click_logout):
        raise PreventUpdate
    if click_authorize and not instance_name:
        raise PreventUpdate
    clicked_button = callback_context.triggered[0]['prop_id'].split('.')[0]
    if clicked_button == 'logout-button':
        return None, True, True, True
    redirect_uri = request.host_url + url_base_path_name[1:] + 'auth'
    client_id, client_secret = Mastodon.create_app(
        'mastodon-link-reader',
        scopes=['read'],
        redirect_uris=redirect_uri,
        api_base_url=f'https://{instance_name}')

    return {
        'client_secret': encode(client_secret),
        'client_id': encode(client_id),
        'instance_name': instance_name
    }, True, True, True


@app.callback([Output('location', 'refresh'),
               Output('location', 'href')],
              State('location', 'href'),
              Input('tokens', 'modified_timestamp'),
              State('tokens', 'data'),
              State('auth-code', 'data'),
              State('access-token', 'data'),
              prevent_initial_call=True)
def update_location(location, ts, tokens_data, auth_code, access_token):
    """Creates and redirects to the authentication url of the mastodon instance"""
    if ('auth' in
            location  #have to check for auth in the url otherwise because this callback fires 
            #at the same time as the auth_token getting set and the other conditionals won't be met
        ) or access_token or auth_code or not tokens_data:
        sleep(1)
        return False, request.host_url + url_base_path_name[1:]
    instance_name = tokens_data['instance_name']
    m = Mastodon(client_id=decode(tokens_data['client_id']),
                 client_secret=decode(tokens_data['client_secret']),
                 api_base_url=f'https://{instance_name}')

    redirect_uri = request.host_url + url_base_path_name[1:] + 'auth'

    url = m.auth_request_url(redirect_uris=redirect_uri, scopes=['read'])

    return True, url


@app.callback(Output('auth-code', 'data'), Input('location', 'search'),
              State('tokens', 'data'), State('auth-code', 'data'),
              State('access-token', 'data'))
def parse_access_code(search, tokens, auth_code, access_token):
    """When bouncing back from the instance with the code in the URL, pull out the code and store it."""
    if access_token:
        raise PreventUpdate
    no_auth_url = request.host_url + url_base_path_name[1:]
    if not search or not search.startswith(
            '?code') or not tokens or not tokens.get(
                'instance_name') or auth_code:
        raise PreventUpdate
    code = parse_qs(search[1:])['code'][0]
    return {'code': encode(code)}


@app.callback(Output('access-token', 'data'), Input('auth-code', 'data'),
              State('tokens', 'data'), State('access-token', 'data'))
def update_final_token(codes, tokens, access_token):
    """Gets the actual useful access token after the code is stored and set from the redirect."""
    if not codes or access_token:
        raise PreventUpdate
    api_base_url = f"https://{tokens['instance_name']}"
    redirect_uri = request.host_url + url_base_path_name[1:] + 'auth'

    m = Mastodon(api_base_url=api_base_url,
                 client_id=decode(tokens['client_id']),
                 client_secret=decode(tokens['client_secret']))
    token = m.log_in(code=decode(codes['code']),
                     redirect_uri=redirect_uri,
                     scopes=['read'])
    return ({'access_token': encode(token)})


@app.callback(
    output=[Output('article-cache', 'data'),
            Output('fs-spinner', 'children')],
    inputs=[
        Input('access-token', 'data'),
        State('tokens', 'data'),
        State('article-cache', 'modified_timestamp'),
        State('article-cache', 'data')
    ],
)
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
    return mydata, ' '


@app.callback(Output('output', 'children'), Input('article-cache', 'data'),
              State('tokens', 'data'))
def update_output(mydata, tokens):
    """Gets the data from local storage and actually makes the web site"""
    if not mydata:
        return dbc.Container()

    api_base_url = f"https://{tokens['instance_name']}"

    return dbc.Container([
        dbc.Row([dbc.Col(make_card(x, api_base_url))]) for x in mydata['posts']
    ],
                         style=STYLE)


if __name__ == "__main__":
    app.run_server(debug=True)