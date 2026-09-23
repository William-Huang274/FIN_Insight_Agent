package io.finsight.business;

import com.nimbusds.jose.*;
import com.nimbusds.jose.crypto.*;
import com.nimbusds.jwt.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.*;

@Component
final class Delegation {
    private final byte[] key;
    Delegation(@Value("${finsight.shared-secret}") String secret) {
        key = secret.getBytes(StandardCharsets.UTF_8);
        if (key.length < 32) throw new IllegalArgumentException("delegation_secret_requires_32_bytes");
    }
    static String digest(byte[] data) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(data)); }
        catch (Exception e) { throw new IllegalStateException(e); }
    }
    String sign(String owner, String method, String path, byte[] body, String operation) throws Exception {
        var now = Instant.now();
        var claims = new JWTClaimsSet.Builder().issuer("finsight-java").audience("finsight-python-intake").subject(owner)
            .issueTime(Date.from(now)).expirationTime(Date.from(now.plusSeconds(60)))
            .claim("method", method).claim("path", path).claim("operation_id", operation).claim("body_sha256", digest(body)).build();
        var token = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), claims);
        token.sign(new MACSigner(key));
        return token.serialize();
    }
    String verify(String header, String method, String path, byte[] body, String operation) throws Exception {
        if (header == null || !header.startsWith("Bearer ") || header.length() > 16384) throw new JOSEException("missing_delegation");
        var token = SignedJWT.parse(header.substring(7));
        if (!JWSAlgorithm.HS256.equals(token.getHeader().getAlgorithm()) || !token.verify(new MACVerifier(key))) throw new JOSEException("invalid_signature");
        var c = token.getJWTClaimsSet();
        var now = Instant.now();
        if (!"finsight-workbench".equals(c.getIssuer()) || !List.of("finsight-java").equals(c.getAudience())
            || c.getSubject() == null || c.getSubject().isBlank() || c.getSubject().length() > 160
            || c.getIssueTime() == null || c.getExpirationTime() == null
            || c.getIssueTime().toInstant().isAfter(now) || !c.getExpirationTime().toInstant().isAfter(now)
            || c.getExpirationTime().getTime() - c.getIssueTime().getTime() > 60000
            || c.getExpirationTime().getTime() <= c.getIssueTime().getTime()
            || !method.equals(c.getStringClaim("method")) || !path.equals(c.getStringClaim("path"))
            || !operation.equals(c.getStringClaim("operation_id"))
            || !digest(body).equals(c.getStringClaim("body_sha256"))) throw new JOSEException("invalid_binding");
        return c.getSubject();
    }
}
