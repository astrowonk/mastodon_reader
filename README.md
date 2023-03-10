
[See the deployed app](https://marcoshuerta.com/dash/mastodon_reader/)

This Dash web app uses the Mastodon API to scan your bookmarks and favorites for links (specifically the `card` attribute which I believe is created when a link preview is generated.)

It should successfully redirect to your instance and back with an `access_token`. All tokens/codes etc are stored in browser local storage but encrypted with [Fernet](https://cryptography.io/en/latest/fernet/) so no other site should be able to do much with them should they somehow access the local storage values. It requests only read-only access.

TODO:

  ~~* Hide/Show the Login/Authorize interface~~
  * Add manual refresh button
  * Limit lookback window by time (i.e. only 30 days, rather than 40 posts)
  * Setting for how far back / how many bookmarks/faves to use. (settings tab?)
  * About / FAQ tab
  * Include boosts as an option?
  * Better CSS and layout