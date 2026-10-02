package pl.serwerplex.status;

import android.content.Context;
import android.util.Log;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/**
 * Radio control over HTTP, port 8098, whole home network (no password, like the status page).
 * GET /radio/state | /radio/play?id=… | /radio/stop | /radio/volume?v=0..100 | /radio/sleep?min=0..
 * Response: radio state as JSON, with a CORS header (the page on port 8099 and other devices).
 */
final class ControlServer extends Thread {
    static final int PORT = 8098;
    private static final String TAG = "StatusControl";
    private static ControlServer instance;
    private final Context ctx;

    private ControlServer(Context ctx) {
        super("control-server");
        this.ctx = ctx.getApplicationContext();
        setDaemon(true);
    }

    static synchronized void ensureStarted(Context c) {
        if (instance == null || !instance.isAlive()) {
            instance = new ControlServer(c);
            instance.start();
        }
    }

    @Override
    public void run() {
        try {
            ServerSocket ss = new ServerSocket();
            ss.setReuseAddress(true);
            ss.bind(new InetSocketAddress(PORT));
            while (true) {
                final Socket s = ss.accept();
                new Thread(new Runnable() {
                    @Override
                    public void run() {
                        handle(s);
                    }
                }, "control-request").start();
            }
        } catch (Exception e) {
            Log.w(TAG, "control server is not running", e);
        }
    }

    private void handle(Socket s) {
        try {
            s.setSoTimeout(5000);
            BufferedReader in = new BufferedReader(new InputStreamReader(s.getInputStream(), StandardCharsets.UTF_8));
            String line = in.readLine();
            if (line == null) return;
            String h;
            while ((h = in.readLine()) != null && !h.isEmpty()) {
                // headers are ignored
            }
            String[] parts = line.split(" ");
            String method = parts[0];
            String target = parts.length > 1 ? parts[1] : "/";
            String path = target.contains("?") ? target.substring(0, target.indexOf('?')) : target;
            Map<String, String> q = query(target);

            if ("OPTIONS".equals(method)) {
                respond(s, 204, "");
                return;
            }
            RadioPlayer radio = RadioPlayer.get(ctx);
            switch (path) {
                case "/radio/state":
                    break;
                case "/radio/play":
                    radio.play(q.getOrDefault("id", ""));
                    break;
                case "/radio/stop":
                    radio.stop("stopped");
                    break;
                case "/radio/volume":
                    radio.setVolume(parseInt(q.get("v"), 50));
                    break;
                case "/radio/sleep":
                    radio.setSleep(parseInt(q.get("min"), 0));
                    break;
                default:
                    respond(s, 404, "{\"error\":\"not found\"}");
                    return;
            }
            respond(s, 200, radio.stateJson());
        } catch (Exception e) {
            Log.w(TAG, "request error", e);
        } finally {
            try {
                s.close();
            } catch (Exception ignored) {
            }
        }
    }

    private static void respond(Socket s, int code, String body) throws Exception {
        byte[] b = body.getBytes(StandardCharsets.UTF_8);
        String status = code == 200 ? "OK" : code == 204 ? "No Content" : "Not Found";
        String head = "HTTP/1.1 " + code + " " + status + "\r\n"
                + "Content-Type: application/json; charset=utf-8\r\n"
                + "Access-Control-Allow-Origin: *\r\n"
                + "Access-Control-Allow-Methods: GET, OPTIONS\r\n"
                + "Cache-Control: no-store\r\n"
                + "Content-Length: " + b.length + "\r\n"
                + "Connection: close\r\n\r\n";
        OutputStream out = s.getOutputStream();
        out.write(head.getBytes(StandardCharsets.US_ASCII));
        out.write(b);
        out.flush();
    }

    private static Map<String, String> query(String target) {
        Map<String, String> m = new HashMap<>();
        int i = target.indexOf('?');
        if (i < 0) return m;
        for (String kv : target.substring(i + 1).split("&")) {
            int e = kv.indexOf('=');
            try {
                if (e > 0) m.put(URLDecoder.decode(kv.substring(0, e), "UTF-8"), URLDecoder.decode(kv.substring(e + 1), "UTF-8"));
            } catch (Exception ignored) {
            }
        }
        return m;
    }

    private static int parseInt(String v, int def) {
        try {
            return Integer.parseInt(v);
        } catch (Exception e) {
            return def;
        }
    }
}
