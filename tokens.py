import spotipy
from spotipy.oauth2 import SpotifyOAuth

sp = SpotifyOAuth(
    client_id="fd5dc9e6022145c6ad3e8241baee4a85",
    client_secret="ea39fb90b76e4617ba3c1dd6336a5778",
    redirect_uri="http://127.0.0.1:3000/callback",
    scope="playlist-modify-public playlist-modify-private"
)

token_info = sp.get_access_token(as_dict=True)
print("REFRESH TOKEN:", token_info["refresh_token"])
