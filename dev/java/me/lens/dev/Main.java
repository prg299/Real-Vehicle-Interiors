package me.lens.dev;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import se.krka.kahlua.integration.LuaReturn;
import se.krka.kahlua.luaj.compiler.LuaCompiler;
import se.krka.kahlua.vm.KahluaTable;
import se.krka.kahlua.vm.KahluaTableIterator;
import zombie.Lua.LuaManager;

/**
 * DEVELOPER TEST MOD ONLY - never shipped with ME: LENS.
 * Runs Lua posted to http://127.0.0.1:18470/lua on the game's main thread, so an
 * isolated test profile can be driven from scripts. Bound to loopback only.
 */
public final class Main {
    static final ConcurrentLinkedQueue<Task> tasks = new ConcurrentLinkedQueue<>();
    private static HttpServer server;

    record Task(String code, int depth, CompletableFuture<String> result) {}

    public static void main(String[] args) throws IOException {
        if (server != null) return;
        me.zed_0xff.zombie_buddy.Exposer.exposeClass(Bones.class);
        me.zed_0xff.zombie_buddy.Exposer.exposeClass(Spawn.class);
        me.zed_0xff.zombie_buddy.Exposer.exposeClass(Media.class);
        me.zed_0xff.zombie_buddy.Exposer.exposeClass(TextInput.class);
        int port = Integer.getInteger("melens.dev.port", 18470);
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 0);
        server.createContext("/lua", Main::handle);
        server.createContext("/status", exchange -> reply(exchange, 200, "{\"ok\":true}"));
        server.setExecutor(null);
        server.start();
        System.out.println("[RealVehicleInteriors_Dev] test Lua endpoint on http://127.0.0.1:" + port + "/lua");
    }

    private static void handle(HttpExchange exchange) throws IOException {
        if (!"POST".equals(exchange.getRequestMethod())) {
            reply(exchange, 405, "{\"error\":\"POST Lua code\"}");
            return;
        }
        String code = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
        int depth = 3;
        String query = exchange.getRequestURI().getQuery();
        if (query != null && query.startsWith("depth=")) {
            depth = Integer.parseInt(query.substring(6).split("&")[0]);
        }
        Task task = new Task(code, depth, new CompletableFuture<>());
        tasks.add(task);
        try {
            reply(exchange, 200, task.result.get(60, TimeUnit.SECONDS));
        } catch (TimeoutException timeout) {
            tasks.remove(task);
            reply(exchange, 504, "{\"error\":\"main thread did not run the task within 60 s\"}");
        } catch (Exception failure) {
            reply(exchange, 500, "{\"error\":" + json(String.valueOf(failure)) + "}");
        }
    }

    /** Called on the main thread every UI update. */
    public static void runTasks() {
        Task task;
        while ((task = tasks.poll()) != null) {
            try {
                Object closure = LuaCompiler.loadstring(task.code, "dev", LuaManager.env);
                LuaReturn ret = LuaManager.caller.protectedCall(LuaManager.thread, closure);
                if (ret.isSuccess()) {
                    task.result.complete("{\"ok\":true,\"result\":" + toJson(ret.isEmpty() ? null : ret.getFirst(), task.depth) + "}");
                } else {
                    task.result.complete("{\"ok\":false,\"error\":" + json(ret.getErrorString()) + ",\"stack\":" + json(ret.getLuaStackTrace()) + "}");
                }
            } catch (Throwable failure) {
                task.result.complete("{\"ok\":false,\"error\":" + json(String.valueOf(failure)) + "}");
            }
        }
    }

    private static String toJson(Object value, int depth) {
        if (value == null) return "null";
        if (value instanceof Boolean) return value.toString();
        if (value instanceof Double d) {
            if (d.isNaN() || d.isInfinite()) return json(d.toString());
            return d == Math.rint(d) && Math.abs(d) < 1e15 ? Long.toString(d.longValue()) : d.toString();
        }
        if (value instanceof Number) return value.toString();
        if (value instanceof KahluaTable table) {
            if (depth <= 0) return json("<table>");
            StringBuilder out = new StringBuilder("{");
            KahluaTableIterator it = table.iterator();
            boolean first = true;
            while (it.advance()) {
                if (!first) out.append(',');
                first = false;
                out.append(json(String.valueOf(it.getKey() instanceof Double d && d == Math.rint(d) ? Long.toString(d.longValue()) : it.getKey())));
                out.append(':').append(toJson(it.getValue(), depth - 1));
            }
            return out.append('}').toString();
        }
        return json(String.valueOf(value));
    }

    static String json(String text) {
        if (text == null) return "null";
        StringBuilder out = new StringBuilder("\"");
        for (char c : text.toCharArray()) {
            switch (c) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (c < 0x20) out.append(String.format("\\u%04x", (int) c));
                    else out.append(c);
                }
            }
        }
        return out.append('"').toString();
    }

    private static void reply(HttpExchange exchange, int status, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=UTF-8");
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(bytes);
        }
    }
}
