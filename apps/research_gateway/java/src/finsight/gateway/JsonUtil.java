package finsight.gateway;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

final class JsonUtil {
    private JsonUtil() {
    }

    static Map<String, Object> readObject(String json) {
        Object value = new Parser(json).parse();
        if (!(value instanceof Map<?, ?> map)) {
            throw new IllegalArgumentException("json_object_required");
        }
        Map<String, Object> result = new LinkedHashMap<>();
        for (Map.Entry<?, ?> entry : map.entrySet()) {
            result.put(String.valueOf(entry.getKey()), entry.getValue());
        }
        return result;
    }

    static String write(Object value) {
        StringBuilder sb = new StringBuilder();
        writeValue(sb, value);
        return sb.toString();
    }

    private static void writeValue(StringBuilder sb, Object value) {
        if (value == null) {
            sb.append("null");
        } else if (value instanceof String text) {
            writeString(sb, text);
        } else if (value instanceof Number || value instanceof Boolean) {
            sb.append(value);
        } else if (value instanceof Map<?, ?> map) {
            sb.append('{');
            boolean first = true;
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                if (!first) {
                    sb.append(',');
                }
                first = false;
                writeString(sb, String.valueOf(entry.getKey()));
                sb.append(':');
                writeValue(sb, entry.getValue());
            }
            sb.append('}');
        } else if (value instanceof Iterable<?> iterable) {
            sb.append('[');
            boolean first = true;
            for (Object item : iterable) {
                if (!first) {
                    sb.append(',');
                }
                first = false;
                writeValue(sb, item);
            }
            sb.append(']');
        } else {
            writeString(sb, String.valueOf(value));
        }
    }

    private static void writeString(StringBuilder sb, String text) {
        sb.append('"');
        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            switch (ch) {
                case '"' -> sb.append("\\\"");
                case '\\' -> sb.append("\\\\");
                case '\b' -> sb.append("\\b");
                case '\f' -> sb.append("\\f");
                case '\n' -> sb.append("\\n");
                case '\r' -> sb.append("\\r");
                case '\t' -> sb.append("\\t");
                default -> {
                    if (ch < 0x20) {
                        sb.append(String.format("\\u%04x", (int) ch));
                    } else {
                        sb.append(ch);
                    }
                }
            }
        }
        sb.append('"');
    }

    private static final class Parser {
        private final String text;
        private int index;

        Parser(String text) {
            this.text = text == null ? "" : text.trim();
        }

        Object parse() {
            Object value = parseValue();
            skipWhitespace();
            if (index != text.length()) {
                throw new IllegalArgumentException("trailing_json_content");
            }
            return value;
        }

        private Object parseValue() {
            skipWhitespace();
            if (index >= text.length()) {
                throw new IllegalArgumentException("unexpected_end_of_json");
            }
            char ch = text.charAt(index);
            if (ch == '"') {
                return parseString();
            }
            if (ch == '{') {
                return parseObject();
            }
            if (ch == '[') {
                return parseArray();
            }
            if (text.startsWith("true", index)) {
                index += 4;
                return Boolean.TRUE;
            }
            if (text.startsWith("false", index)) {
                index += 5;
                return Boolean.FALSE;
            }
            if (text.startsWith("null", index)) {
                index += 4;
                return null;
            }
            return parseNumber();
        }

        private Map<String, Object> parseObject() {
            expect('{');
            Map<String, Object> map = new LinkedHashMap<>();
            skipWhitespace();
            if (peek('}')) {
                index++;
                return map;
            }
            while (true) {
                String key = parseString();
                skipWhitespace();
                expect(':');
                Object value = parseValue();
                map.put(key, value);
                skipWhitespace();
                if (peek('}')) {
                    index++;
                    return map;
                }
                expect(',');
            }
        }

        private List<Object> parseArray() {
            expect('[');
            List<Object> list = new ArrayList<>();
            skipWhitespace();
            if (peek(']')) {
                index++;
                return list;
            }
            while (true) {
                list.add(parseValue());
                skipWhitespace();
                if (peek(']')) {
                    index++;
                    return list;
                }
                expect(',');
            }
        }

        private String parseString() {
            expect('"');
            StringBuilder sb = new StringBuilder();
            while (index < text.length()) {
                char ch = text.charAt(index++);
                if (ch == '"') {
                    return sb.toString();
                }
                if (ch != '\\') {
                    sb.append(ch);
                    continue;
                }
                if (index >= text.length()) {
                    throw new IllegalArgumentException("bad_json_escape");
                }
                char esc = text.charAt(index++);
                switch (esc) {
                    case '"' -> sb.append('"');
                    case '\\' -> sb.append('\\');
                    case '/' -> sb.append('/');
                    case 'b' -> sb.append('\b');
                    case 'f' -> sb.append('\f');
                    case 'n' -> sb.append('\n');
                    case 'r' -> sb.append('\r');
                    case 't' -> sb.append('\t');
                    case 'u' -> {
                        if (index + 4 > text.length()) {
                            throw new IllegalArgumentException("bad_unicode_escape");
                        }
                        String hex = text.substring(index, index + 4);
                        index += 4;
                        sb.append((char) Integer.parseInt(hex, 16));
                    }
                    default -> throw new IllegalArgumentException("bad_json_escape");
                }
            }
            throw new IllegalArgumentException("unterminated_json_string");
        }

        private Number parseNumber() {
            int start = index;
            if (peek('-')) {
                index++;
            }
            while (index < text.length() && Character.isDigit(text.charAt(index))) {
                index++;
            }
            boolean floating = false;
            if (peek('.')) {
                floating = true;
                index++;
                while (index < text.length() && Character.isDigit(text.charAt(index))) {
                    index++;
                }
            }
            if (peek('e') || peek('E')) {
                floating = true;
                index++;
                if (peek('+') || peek('-')) {
                    index++;
                }
                while (index < text.length() && Character.isDigit(text.charAt(index))) {
                    index++;
                }
            }
            if (start == index) {
                throw new IllegalArgumentException("bad_json_value");
            }
            String raw = text.substring(start, index);
            return floating ? Double.parseDouble(raw) : Long.parseLong(raw);
        }

        private void skipWhitespace() {
            while (index < text.length() && Character.isWhitespace(text.charAt(index))) {
                index++;
            }
        }

        private boolean peek(char expected) {
            return index < text.length() && text.charAt(index) == expected;
        }

        private void expect(char expected) {
            skipWhitespace();
            if (!peek(expected)) {
                throw new IllegalArgumentException("expected_json_char_" + expected);
            }
            index++;
        }
    }
}
