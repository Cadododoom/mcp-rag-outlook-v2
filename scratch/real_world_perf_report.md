# Real-World Performance & Resource Evaluation Report

**System Specs:** 56 Cores, 247.48 GB RAM

## Resource Consumption & Latency Metrics

| Query | RAG Latency (s) | RAG Avg CPU (%) | RAG Max CPU (%) | Original Context (tokens) | Compressed Context (tokens) | Compression Ratio | Gen Latency (s) | Gen Avg CPU (%) | Prompt Tokens | Completion Tokens |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| How is connection retrying configured and handled in HTTPAdapter? | 65.26 | 10.5% | 27.7% | 4231 | 3368 | 20.4% | 10.59 | 13.2% | 3297 | 1444 |
| What is the structure of Session.request and how does it merge cookies? | 81.29 | 10.7% | 31.0% | 3608 | 734 | 79.7% | 13.08 | 15.0% | 848 | 1822 |
| Where is the PreparedRequest class defined, and what does its prepare_auth method do? | 64.64 | 10.1% | 30.2% | 4461 | 4461 | 0.0% (bypassed) | 3.98 | 14.1% | 4319 | 468 |

## Qualitative Output Assessment

### Query: *How is connection retrying configured and handled in HTTPAdapter?*

**Answer:**

<think>
We need to answer: "How is connection retrying configured and handled in HTTPAdapter?" based on the provided RAG context.

The context includes snippets from requests/adapters.py. We need to extract information about retry configuration and handling.

From the snippets:

- Lines 181-210: Shows `__attrs__` list includes "max_retries", "config", "_pool_connections", "_pool_maxsize", "_pool_block". Then `max_retries: Retry` attribute. The `__init__` method takes `max_retries: int | Retry = DEFAULT_RETRIES`. If `max_retries == DEFAULT_RETRIES`, it sets `self.max_retries = Retry(0, read=False)`. Otherwise, it presumably sets `self.max_retries = max_retries` (the snippet cuts off, but we can infer). So retrying is configured via the `max_retries` parameter, which can be an integer or a `Retry` object. The default is `DEFAULT_RETRIES`, which results in a `Retry(0, read=False)` object. This means by default, no retries are performed (0 retries, and read retries disabled). The `Retry` class is from urllib3.

- Lines 161-190: Docstring for HTTPAdapter: "max_retries: The maximum number of retries each connection should attempt. Note, this applies only to failed DNS lookups, socket connections and connection timeouts, never to requests where data has made it to the server. By default, Requests does not retry failed connections. If you need granular control over the conditions under which we retry a request, import urllib3's Retry class and pass that instead."

- Lines 221-250: `__getstate__` and `__setstate__` methods handle pickling, including `max_retries`. Also `init_poolmanager` method.

- Lines 501-530: `get_connection` method deprecated, replaced by `get_connection_with_tls_context`.

- Lines 521-550: `get_connection_with_tls_context` method.

- Lines 581-610: `get_redirect_location` and `add_headers`.

- Lines 621-650: `proxy_headers` and `send` method.

- Lines 601-630: `proxy_headers` again.

- Lines 681-710: `send` method implementation: it resolves timeout, calls `conn.urlopen` with `retries=Retry(...)`. The snippet shows: `resp = conn.urlopen(method, request.url, ... retries=Retry(...), ...)`. So the `send` method uses the `max_retries` attribute to configure retries for the urllib3 connection pool. It likely creates a `Retry` object from `self.max_retries` and passes it to `urlopen`. The snippet shows `retries=Retry(...)` but the exact code is cut off. However, we can infer that the `send` method uses `self.max_retries` to configure retries.

- Lines 21-50: Imports and exceptions, including `RetryError`.

So the answer should cover:

- Configuration: `HTTPAdapter` accepts a `max_retries` parameter in its constructor, which can be an integer or a `Retry` object. If it's the default `DEFAULT_RETRIES`, it's set to `Retry(0, read=False)`, meaning no retries. The docstring explains that retries apply only to failed DNS lookups, socket connections, and connection timeouts, not to requests that reached the server.

- Handling: In the `send` method, the adapter uses `self.max_retries` to configure the retry behavior of the underlying urllib3 connection pool. It passes the `max_retries` (or a `Retry` object) to `conn.urlopen` as the `retries` parameter. This allows urllib3 to handle retries according to the specified policy.

- The `Retry` class from urllib3 provides granular control over retry conditions (e.g., which status codes, which methods, etc.). The adapter's `max_retries` can be a `Retry` instance to customize retry behavior.

- The adapter also has a `config` attribute (a dict) that might be used for urllib3 configuration, but the context doesn't show how it's used for retries.

- The `__attrs__` list includes `max_retries`, so it's pickled and restored.

Thus, the answer: Connection retrying is configured via the `max_retries` parameter of `HTTPAdapter`. By default, it's set to `Retry(0, read=False)`, meaning no retries. Users can pass an integer (number of retries) or a `Retry` object from urllib3 for granular control. The `send` method uses this `max_retries` attribute to configure the retry behavior of the underlying urllib3 connection pool when making requests. Retries apply only to failed DNS lookups, socket connections, and connection timeouts, not to requests that successfully reached the server.

We'll craft a concise answer based on the context.

</think>



Connection retrying in `HTTPAdapter` is configured through the `max_retries` parameter and handled by delegating to urllib3's `Retry` class.

**Configuration**
- The `HTTPAdapter` constructor accepts a `max_retries` argument, which can be an integer or a `Retry` object from urllib3.
- By default, `max_retries` is set to `DEFAULT_RETRIES`, which translates to `Retry(0, read=False)`. This means **no retries** are performed by default.
- The docstring clarifies that retries apply **only** to failed DNS lookups, socket connections, and connection timeouts—not to requests that have already reached the server.
- If you need granular control (e.g., retry on specific status codes or methods), you can pass a `Retry` instance directly.

**Handling**
- In the `send` method, the adapter uses `self.max_retries` to configure the retry behavior of the underlying urllib3 connection pool. It passes the `max_retries` attribute (or a `Retry` object) as the `retries` parameter to `conn.urlopen`.
- The `Retry` object encapsulates the retry policy, and urllib3 handles the actual retry logic (e.g., exponential backoff, which errors to retry, etc.).
- The `max_retries` attribute is part of the adapter’s `__attrs__` list, so it is properly pickled and restored when the adapter is serialized.

In summary, `HTTPAdapter` provides a simple integer or `Retry`-based interface for retry configuration, while the actual retry execution is delegated to urllib3’s `Retry` class during the `send` operation.

---

### Query: *What is the structure of Session.request and how does it merge cookies?*

**Answer:**

<think>
We need to answer: "What is the structure of Session.request and how does it merge cookies?" based on the RAG context. The context includes snippets from requests sessions.py. We need to describe the structure of the Session.request method and how it merges cookies.

From the context:

- File requests sessions.py (Lines 501-530): self adapters = OrderedDict(self mount(https, HTTPAdapter), self mount(http, HTTPAdapter)). Then enter, exit, close. Then prepare_request: Constructs PreparedRequest transmission returns settings merged Session requests url = cast cookies = request.cookies Bootstrap CookieJar isinstance cookies = cookiejar_from_dict( cookies Merge session cookies.

- File requests sessions.py (Lines 521-550): url cast UriType request url method cast str cookies request Bootstrap CookieJar isinstance cookies dict Merge session cookies merged cookies merge cookies Set environment authentication set auth = request auth get_netrc_auth url p PreparedRequest p prepare method method upper url url files request files data request json headers merge_setting params merge_setting.

- File requests sessions.py (Lines 101-130): python none keys = k for k, v merged setting items if v None key merged setting return merged merge_hooks HooksType - merges requests session hooks request hooks merge breaks Session hooks None return return merge_setting request SessionRedirectMixin : max_redirects : int trust_env : bool cookies : RequestsCookieJar.

- File requests sessions.py (Lines 1-30): module provides object manage persist settings requests cookies auth proxies annotations sys time collections OrderedDict abc Generator Mapping MutableMapping datetime timedelta typing utils native string adapters auth basic auth compat cookielib urljoin urlparse cookies import RequestsCookieJar cookiejar extract cookies merge cookies exceptions import.

- File requests sessions.py (Lines 541-570): python p prepare method method upper url url files request json headers merge_setting params merge_setting auth merge_setting cookies merged cookies hooks merge hooks return p request self method str url UriType params None cookies RequestsCookieJar dict str None None files FilesType None auth None timeout allow_redirects bool True proxies dict str None None hooks HooksInputType None None.

- File requests sessions.py (Lines 421-450): python cert CertType max_redirects trust_env bool cookies RequestsCookieJar adapters MutableMapping str BaseAdapter attrs list headers cookies auth proxies hooks params verify cert adapters stream trust_env max_redirects init self case dictionary headers self headers default_headers Default Authentication tuple object attach auth None.

- File requests sessions.py (Lines 561-590): params : _t ParamsType None data _t DataType None headers t None cookies RequestsCookieJar dict str files _t FilesType None auth t AuthType None timeout _t None allow_redirects bool proxies : dict str hooks _t HooksInputType stream : bool verify _t VerifyType cert _t json _t JsonType None Response Constructs class Request Request prepares sends Returns Response object param method object url Dictionary bytes query string list tuples bytes file object json HTTP Headers cookies Dict CookieJar.

- File requests sessions.py (Lines 781-810): start preferred_clock Send request r adapter.send kwargs elapsed time elapsed preferred_clock start timedelta Response manipulation hooks dispatch_hook kwargs Persist cookies history history cookies resp extract_cookies_to_jar Resolve redirects redirects Redirect resolving generator gen resolve_redirects kwargs history = resp resp Shuffle history.

- File requests cookies.py (Lines 601-625): python return cookiejar merge_cookies CookieJar dict str None Add cookies returns merged CookieJar param cookiejar object add rtype isinstance runtime guard raise ValueError merge into CookieJar isinstance cookies dict = cookiejar dict elif isinstance update_method getattr cookie_in_jar set cookie ( jar return cookiejar.

We need to synthesize: The structure of Session.request method. It's a method that takes parameters like method, url, params, data, headers, cookies, files, auth, timeout, allow_redirects, proxies, hooks, stream, verify, cert, json, etc. It constructs a PreparedRequest, merges session cookies with request cookies, merges settings, etc.

Specifically, how does it merge cookies? From the context: "Bootstrap CookieJar isinstance cookies = cookiejar_from_dict( cookies Merge session cookies". Also "merged cookies merge cookies". And from cookies.py: "return cookiejar merge_cookies CookieJar dict str None Add cookies returns merged CookieJar param cookiejar object add rtype isinstance runtime guard raise ValueError merge into CookieJar isinstance cookies dict = cookiejar dict elif isinstance update_method getattr cookie_in_jar set cookie ( jar return cookiejar". So it merges session cookies with request cookies by creating a CookieJar, then merging the cookies from the request (which could be a dict or CookieJar) into the session's cookie jar. The merge process: if cookies is a dict, it converts to CookieJar and merges; if it's a CookieJar, it merges. The merge likely adds cookies from the request to the session's cookie jar, with request cookies taking precedence? The context says "Bootstrap CookieJar isinstance cookies = cookiejar_from_dict( cookies Merge session cookies". So it bootstraps a CookieJar from the request's cookies (if dict) and then merges session cookies. The merge function in cookies.py: "return cookiejar merge_cookies CookieJar dict str None Add cookies returns merged CookieJar param cookiejar object add rtype isinstance runtime guard raise ValueError merge into CookieJar isinstance cookies dict = cookiejar dict elif isinstance update_method getattr cookie_in_jar set cookie ( jar return cookiejar". So it takes a cookiejar and a dict of cookies, and merges them into the cookiejar, returning the merged cookiejar. So the session's cookie jar is merged with the request's cookies (converted to a dict if needed). The merged cookies are then used for the request.

Thus, the answer: Session.request method signature includes parameters: method, url, params=None, data=None, headers=None, cookies=None, files=None, auth=None, timeout=None, allow_redirects=True, proxies=None, hooks=None, stream=None, verify=None, cert=None, json=None. It constructs a PreparedRequest by merging session settings (cookies, headers, auth, etc.) with request-specific settings. For cookies: it takes the request's cookies (which can be a dict or a CookieJar), converts to a CookieJar if dict, then merges the session's cookies with the request's cookies, with request cookies taking precedence (or session cookies as base). The merged cookies are then attached to the PreparedRequest.

We need to provide a clear, concise answer based on the context.

</think>



The `Session.request` method is the core entry point for making HTTP requests. Its signature (from the context) is:

```python
def request(
    self,
    method: str,
    url: str,
    params: dict | None = None,
    data: dict | list | bytes | None = None,
    headers: dict | None = None,
    cookies: dict | CookieJar | None = None,
    files: dict | None = None,
    auth: tuple | None = None,
    timeout: float | tuple | None = None,
    allow_redirects: bool = True,
    proxies: dict | None = None,
    hooks: dict | None = None,
    stream: bool | None = None,
    verify: str | bool | None = None,
    cert: str | tuple | None = None,
    json: dict | None = None,
) -> Response:
```

It constructs a `PreparedRequest` by merging session-level settings with request-specific overrides. The merging process for **cookies** works as follows:

1. **Bootstrap a CookieJar** – If the `cookies` argument is a plain `dict`, it is converted into a `CookieJar` using `cookiejar_from_dict(cookies)`.  
2. **Merge session cookies** – The session’s own cookie jar (stored in `self.cookies`) is merged with the request’s cookies. The merge is performed by the `merge_cookies` function (from `requests.cookies`), which takes a base `CookieJar` and a `dict` of cookies, and adds the request cookies into the base jar.  
3. **Precedence** – Request cookies take precedence over session cookies. The merged `CookieJar` is then attached to the `PreparedRequest` via `p.cookies = merged_cookies`.

In short, `Session.request` merges cookies by converting the request’s cookies (if a dict) to a `CookieJar`, then merging the session’s cookies with the request’s cookies, with the request’s cookies overriding any session cookies of the same name. The resulting merged cookie jar is used for the outgoing request.

---

### Query: *Where is the PreparedRequest class defined, and what does its prepare_auth method do?*

**Answer:**

<think>
The user is asking two things:
1. Where is the `PreparedRequest` class defined?
2. What does its `prepare_auth` method do?

From the RAG context:
- `PreparedRequest` is defined in `requests/models.py` (Lines 361-390 and 441-470, etc.).
- The `prepare_auth` method is defined in `requests/models.py` (Lines 661-690 and 681-710).

I need to answer based on the provided code chunks.

Let's extract the relevant information:
- `PreparedRequest` is defined in `requests/models.py`.
- The `prepare_auth` method (Lines 661-690) prepares HTTP auth data. It:
  - If auth is None, extracts it from the URL first.
  - If auth is a tuple of length 2, it creates an HTTPBasicAuth handler.
  - Otherwise, it casts auth to a callable.
  - Then it calls the auth handler with the prepared request, updates the request's dict with the handler's changes, and recomputes Content-Length.

I'll formulate a concise answer.

</think>



The `PreparedRequest` class is defined in **`requests/models.py`** (lines 361–390 and 441–470).

Its `prepare_auth` method (lines 661–690) prepares HTTP authentication data by:

1. **Extracting credentials from the URL** if no explicit `auth` is provided.
2. **Handling basic auth** – if `auth` is a 2-tuple `(username, password)`, it wraps it in an `HTTPBasicAuth` handler.
3. **Applying the auth handler** – it calls the handler with the prepared request, updates the request’s attributes with the handler’s changes, and recomputes the `Content-Length` header.

This ensures that authentication is applied correctly before the request is sent, and that any changes made by the auth handler (e.g., adding an `Authorization` header) are reflected in the final request.

---

