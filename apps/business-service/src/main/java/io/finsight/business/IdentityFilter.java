package io.finsight.business;

import jakarta.servlet.*;
import jakarta.servlet.http.*;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import java.io.*;

@Component
final class IdentityFilter extends OncePerRequestFilter {
    private final Delegation delegation;
    IdentityFilter(Delegation delegation) { this.delegation = delegation; }
    @Override protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain) throws ServletException, IOException {
        response.setCharacterEncoding("UTF-8");
        response.setHeader("Cache-Control", "no-store");
        byte[] bytes = request.getInputStream().readNBytes(65537);
        if (bytes.length > 65536) { response.sendError(413); return; }
        String path = request.getRequestURI() + (request.getQueryString() == null ? "" : "?" + request.getQueryString());
        String owner;
        try { owner = delegation.verify(request.getHeader("Authorization"), request.getMethod(), path, bytes, java.util.Objects.requireNonNullElse(request.getHeader("Idempotency-Key"), "")); }
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
