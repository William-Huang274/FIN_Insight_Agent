package io.finsight.business;

import com.nimbusds.jose.*;
import com.nimbusds.jose.crypto.MACVerifier;
import com.nimbusds.jwt.SignedJWT;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.List;

/** Separate workload credential: cannot impersonate a user on business routes. */
@Component
final class RuntimeDelegation {
    private final byte[] key;
    RuntimeDelegation(@Value("${finsight.runtime-secret:}") String secret,
                      @Value("${finsight.shared-secret}") String businessSecret) {
        key=secret.getBytes(StandardCharsets.UTF_8);
        if(key.length!=0&&(key.length<32||secret.equals(businessSecret)))
            throw new IllegalArgumentException("runtime_secret_must_be_distinct_and_at_least_32_bytes");
    }
    void verify(String header,String method,String path,byte[] body) throws Exception {
        if(key.length==0||header==null||!header.startsWith("Bearer ")||header.length()>16384)throw new JOSEException("missing_runtime_delegation");
        var token=SignedJWT.parse(header.substring(7));
        if(!JWSAlgorithm.HS256.equals(token.getHeader().getAlgorithm())||!token.verify(new MACVerifier(key)))throw new JOSEException("invalid_signature");
        var c=token.getJWTClaimsSet();var now=Instant.now();
        if(!"finsight-agent-runtime".equals(c.getIssuer())||!List.of("finsight-java-organization-runtime").equals(c.getAudience())
            ||!"finsight-agent-runtime".equals(c.getSubject())||c.getIssueTime()==null||c.getExpirationTime()==null
            ||c.getIssueTime().toInstant().isAfter(now)||!c.getExpirationTime().toInstant().isAfter(now)
            ||c.getExpirationTime().getTime()-c.getIssueTime().getTime()>60000
            ||c.getExpirationTime().getTime()<=c.getIssueTime().getTime()
            ||!method.equals(c.getStringClaim("method"))||!path.equals(c.getStringClaim("path"))
            ||!Delegation.digest(body).equals(c.getStringClaim("body_sha256")))throw new JOSEException("invalid_runtime_binding");
    }
}
