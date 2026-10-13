package io.finsight.business;

import jakarta.servlet.*;
import jakarta.servlet.http.*;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import java.io.*;

@Component
final class IdentityFilter extends OncePerRequestFilter {
    private final Delegation delegation;
    private final RuntimeDelegation runtime;
    IdentityFilter(Delegation delegation,RuntimeDelegation runtime) { this.delegation = delegation; this.runtime=runtime; }
    @Override protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain) throws ServletException, IOException {
        response.setCharacterEncoding("UTF-8");
        response.setHeader("Cache-Control", "no-store");
        // API path segments are static names and UUIDs. Reject encoded/matrix/dot
        // aliases before selecting an identity domain; Spring may normalize them.
        String rawPath=request.getRequestURI();
        if(!rawPath.matches("/v1/[A-Za-z0-9/_-]+")||rawPath.contains("//")) {
            response.setStatus(400);return;
        }
        byte[] bytes = request.getInputStream().readNBytes(65537);
        if (bytes.length > 65536) { response.sendError(413); return; }
        String path = request.getRequestURI() + (request.getQueryString() == null ? "" : "?" + request.getQueryString());
        String owner;
        try {
            if(rawPath.startsWith("/v1/runtime/")) {
                runtime.verify(request.getHeader("Authorization"),request.getMethod(),path,bytes);
                owner=null; // A workload never supplies a user identity; the binding does.
            } else owner = delegation.verify(request.getHeader("Authorization"), request.getMethod(), path, bytes, java.util.Objects.requireNonNullElse(request.getHeader("Idempotency-Key"), ""));
        }
        catch (Exception e) { response.setStatus(401); response.setContentType("application/json"); response.getWriter().write("{\"detail\":\"无效的业务委托凭证\"}"); return; }
        request.setAttribute("owner", owner);
        request.setAttribute("originalBody", bytes);
        var wrapped = new HttpServletRequestWrapper(request) {
            @Override public ServletInputStream getInputStream() {
                var stream = new ByteArrayInputStream(bytes);
                return new ServletInputStream() {
                    @Override public int read() { return stream.read(); }
                    @Override public boolean isFinished() { return stream.available() == 0; }
                    @Override public boolean isReady() { return true; }
                    @Override public void setReadListener(ReadListener listener) { throw new UnsupportedOperationException(); }
                };
            }
            @Override public BufferedReader getReader() { return new BufferedReader(new InputStreamReader(getInputStream(), java.nio.charset.StandardCharsets.UTF_8)); }
        };
        chain.doFilter(wrapped, response);
    }
}
