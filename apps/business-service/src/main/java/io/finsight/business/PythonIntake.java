package io.finsight.business;

import com.fasterxml.jackson.databind.*;
import org.apache.hc.client5.http.classic.methods.HttpUriRequestBase;
import org.apache.hc.client5.http.config.RequestConfig;
import org.apache.hc.client5.http.impl.classic.*;
import org.apache.hc.core5.http.ContentType;
import org.apache.hc.core5.http.io.entity.*;
import org.apache.hc.core5.util.Timeout;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.UUID;

@Component
class PythonIntake implements AutoCloseable {
    record Reply(int status, JsonNode body) {}
    private final String base;
    private final Delegation delegation;
    private final ObjectMapper json;
    private final CloseableHttpClient client;
    PythonIntake(@Value("${finsight.python-url}") String base, Delegation delegation, ObjectMapper json) {
        URI uri = URI.create(base);
        if (!"http".equals(uri.getScheme()) || !("127.0.0.1".equals(uri.getHost()) || "localhost".equals(uri.getHost()))
            || uri.getUserInfo() != null || uri.getQuery() != null || uri.getFragment() != null
            || !(uri.getPath().isEmpty() || uri.getPath().equals("/"))) throw new IllegalArgumentException("python_intake_requires_loopback_url");
        this.base = base.replaceAll("/$", ""); this.delegation = delegation; this.json = json;
        client = HttpClients.custom().disableAutomaticRetries().disableRedirectHandling()
            .setDefaultRequestConfig(RequestConfig.custom().setConnectionRequestTimeout(Timeout.ofSeconds(3))
                .setConnectTimeout(Timeout.ofSeconds(3)).setResponseTimeout(Timeout.ofSeconds(20)).build()).build();
    }
    Reply request(String owner, String method, String suffix, String body, UUID operation) {
        String path = "/api/v1/internal-research/" + suffix;
        byte[] bytes = body == null ? new byte[0] : body.getBytes(StandardCharsets.UTF_8);
        try {
            var request = new HttpUriRequestBase(method, URI.create(base + path));
            request.setHeader("Authorization", "Bearer " + delegation.sign(owner, method, path, bytes, operation == null ? "" : operation.toString()));
            request.setHeader("X-Workbench-Request", "1");
            if (operation != null) request.setHeader("Idempotency-Key", operation.toString());
            if (body != null) request.setEntity(new ByteArrayEntity(bytes, ContentType.APPLICATION_JSON));
            return client.execute(request, response -> {
                byte[] content = response.getEntity().getContent().readNBytes(262145);
                if (content.length > 262144) throw new java.io.IOException("response_too_large");
                return new Reply(response.getCode(), json.readTree(content));
            });
        } catch (Exception e) { throw new IntakeUnavailable(); }
    }
    void authorize(String owner, UUID project) {
        var result = request(owner, "GET", "projects/" + project, null, null);
        if (result.status() == 404 || result.status() == 403) throw ApiFailure.missing();
        if (result.status() != 200) throw new IntakeUnavailable();
    }
    @Override public void close() throws java.io.IOException { client.close(); }
}
