using System;
using Microsoft.AspNetCore.Http.Metadata;

namespace Readarr.Http.Frontend
{
    /// <summary>
    /// Re-enables the cookie-authentication redirect to the login page on an
    /// endpoint. [ApiController] implies IDisableCookieRedirectMetadata, which
    /// makes an unauthenticated browser request return 401 instead of being
    /// sent to /login; the UI controller serves HTML, so it needs the redirect.
    /// </summary>
    [AttributeUsage(AttributeTargets.Class | AttributeTargets.Method)]
    public sealed class AllowCookieRedirectAttribute : Attribute, IAllowCookieRedirectMetadata
    {
    }
}
