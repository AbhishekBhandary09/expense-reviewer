import ssl
import urllib3
import warnings
import requests

# Disable SSL verification globally for standard library ssl calls
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

# Monkeypatch requests to globally disable SSL verification
original_request = requests.Session.request
def unverified_request(*args, **kwargs):
    kwargs['verify'] = False
    return original_request(*args, **kwargs)
requests.Session.request = unverified_request

# Disable warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
