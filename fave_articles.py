import dash_bootstrap_components as dbc
from dash import html, dcc
import datetime


def get_min_id(next_page):
    if isinstance(next_page, list) and len(next_page) != 0:
        if hasattr(next_page, '_pagination_prev'):
            return next_page._pagination_prev['min_id']
        else:
            return None


def get_posts(mastodon,
              fave_limit=40,
              bookmark_limit=40,
              min_fave_id=None,
              min_bookmark_id=None):
    print('retrieving data from mastodon api')

    if not min_fave_id:
        favorites = mastodon.favourites(limit=fave_limit)
    else:
        favorites = mastodon.favourites(min_id=min_fave_id)
    if not min_bookmark_id:
        bookmarks = mastodon.bookmarks(limit=bookmark_limit)
    else:
        bookmarks = mastodon.bookmarks(min_id=min_bookmark_id)

    posts = favorites + bookmarks
    print(f"Retrieved {len(posts)} new posts.")
    return {
        'fave_id_pagination': get_min_id(favorites) or min_fave_id,
        'bookmark_id_pagination': get_min_id(bookmarks) or min_bookmark_id,
        'posts': posts,
    }


def get_first_item(l):
    if l:
        return l[0]['id']


def process_posts(posts):
    out = []
    for post in (x for x in posts if x.get('card')):
        rec = post['card']
        attachment_url = None
        if attachments := post.get('media_attachments'):
            attachment_url = attachments[0]['preview_url']
        interactions = post['replies_count'] + post['reblogs_count'] + post[
            'favourites_count']
        rec.update({
            'id': post['id'],
            'date': post['created_at'],
            'account': post['account']['acct'],
            'display_name': post['account']['display_name'],
            'status_url': post['url'],
            'interaction_count': interactions,
            'atachment_image_url': attachment_url,
            'favorite': post['favourited'],
            'bookmark': post['bookmarked']
        })
        out.append(rec)
    return out


def make_icon(row):
    if row['favorite']:
        return html.I(className="bi bi-star-fill",
                      style={
                          'float': 'right',
                          'display': 'inline-block'
                      })
    elif row['bookmark']:
        return html.I(className="bi bi-bookmark-fill",
                      style={
                          'float': 'right',
                          'display': 'inline-block'
                      })


def make_card(row, host):
    myurl = f"{host}/authorize_interaction?uri={row['status_url']}"
    if len(row['description']) > 200:
        desc = row['description'][:200] + "..."
    else:
        desc = row['description']
    current_tz = datetime.datetime.now().astimezone().tzinfo
    mydate = datetime.datetime.fromisoformat(
        row['date']).astimezone(current_tz).strftime("%b %-d, %Y %-I:%M%p")

    card_content = [
        dbc.CardHeader([
            html.Div([
                dcc.Markdown(
                    f"{mydate}, via [{row['account']}]({myurl}) - *{row['display_name']}*",
                    style={'display': 'inline-block'}),
                make_icon(row)
            ], )
        ]),
        dbc.CardBody([
            html.H5(row['title'], className="card-title"),
            html.P(
                desc,
                className="card-text",
            ),
            dbc.CardLink("Go to Article", href=row['url'], target='_blank')
        ]),
    ]
    if row['atachment_image_url'] or row['image']:
        card_content.append(
            html.A(
                dbc.CardImg(src=row['atachment_image_url'] or row['image'],
                            top=True,
                            style={
                                'height': '15vw',
                                'width': '100%',
                                'object-fit': 'scale-down'
                            }),
                href=row['url'],
                target='_blank',
            ))
    return dbc.Card(card_content,
                    style={
                        'margin-bottom': '2em',
                    },
                    className="w-85 mb-3")


def get_processed_data(
    mastodon,
    min_fave_id=None,
    min_bookmark_id=None,
):

    posts = get_posts(mastodon,
                      min_fave_id=min_fave_id,
                      min_bookmark_id=min_bookmark_id)
    thelist = process_posts(posts['posts'])
    thelist.sort(key=lambda x: x['date'], reverse=True)
    posts['posts'] = thelist
    return posts
