package me.lens.rv;

import java.util.Arrays;
import java.util.Comparator;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.VarHandle;
import org.joml.Vector3f;
import zombie.characters.IsoPlayer;
import zombie.iso.IsoCamera;
import zombie.iso.IsoUtils;
import zombie.vehicles.BaseVehicle;
import zombie.iso.weather.fx.IsoWeatherFX;
import zombie.iso.weather.fx.ParticleRectangle;
import zombie.iso.weather.fx.WeatherParticle;

/** Adds the exposed cabin to the game's weather mask, without changing world squares. */
public final class Weather {
    private record Room(float[] ring, float floor, float ceiling) {}
    private record Point(float x, float y) {}
    private static Room room;
    // Developer A/B capture only; no player option or saved state.
    static boolean enabled = true;
    private static long draws;
    private static int lastPoints;
    private static Point[] activeHull;
    private static float minX, minY, maxX, maxY;
    private static long tested, sheltered;
    private static long scopes;
    private static final VarHandle RECTANGLE_ID;
    private static final VarHandle PARTICLE_BOUNDS;
    static {
        try {
            var lookup = MethodHandles.lookup();
            RECTANGLE_ID = MethodHandles.privateLookupIn(ParticleRectangle.class, lookup)
                    .findVarHandle(ParticleRectangle.class, "id", int.class);
            PARTICLE_BOUNDS = MethodHandles.privateLookupIn(WeatherParticle.class, lookup)
                    .findVarHandle(WeatherParticle.class, "bounds", org.lwjgl.util.Rectangle.class);
        } catch (ReflectiveOperationException failure) {
            throw new ExceptionInInitializerError(failure);
        }
    }

    private Weather() {}

    public static void setRoom(String polygon, double floor, double ceiling) {
        if (polygon == null || polygon.isBlank()) { clear(); return; }
        String[] corners = polygon.split(";");
        if (corners.length < 3 || corners.length > 256 || !Double.isFinite(floor)
                || !Double.isFinite(ceiling) || ceiling <= floor) { clear(); return; }
        float[] ring = new float[corners.length * 2];
        for (int i = 0; i < corners.length; i++) {
            String[] pair = corners[i].split(",");
            if (pair.length != 2) { clear(); return; }
            for (int j = 0; j < 2; j++) {
                float value = Float.parseFloat(pair[j]);
                if (!Float.isFinite(value)) { clear(); return; }
                ring[i * 2 + j] = value;
            }
        }
        room = new Room(ring, (float) floor, (float) ceiling);
    }

    public static void clear() { room = null; }

    public static boolean sheltered(IsoPlayer player) {
        return enabled && room != null && player != null && RV.cutVehicle != null
                && player.getVehicle() == RV.cutVehicle;
    }

    /** Capture this camera's cabin before its precipitation particles are queued. */
    public static void beginParticles(ParticleRectangle rectangle) {
        scopes++;
        activeHull = null;
        if (ViewpointCompat.active()) return;
        int id = (int) RECTANGLE_ID.get(rectangle);
        int playerIndex = IsoCamera.frameState.playerIndex;
        if ((id != IsoWeatherFX.snowId && id != IsoWeatherFX.rainId)
                || playerIndex < 0 || playerIndex >= IsoPlayer.players.length
                || !sheltered(IsoPlayer.players[playerIndex])) return;
        BaseVehicle vehicle = RV.cutVehicle;
        Room r = room;
        if (vehicle.getScript() == null || vehicle.getScript().getModel() == null) return;
        Vector3f offset = vehicle.getScript().getModel().getOffset();
        Vector3f world = new Vector3f();
        float base = vehicle.getWorldPos(0, 0, 0, world).z;
        Point[] points = new Point[r.ring.length];
        int count = 0;
        // Project both floor and cut wall height: furniture and the player also need shelter.
        for (float height : new float[]{r.floor, r.ceiling}) {
            for (int i = 0; i < r.ring.length; i += 2) {
                vehicle.getWorldPos(offset.x + r.ring[i], offset.y + height,
                        offset.z + r.ring[i + 1], world);
                float z = base + (offset.y + height) / 2.44949f;
                points[count++] = new Point(
                        IsoUtils.XToScreen(world.x, world.y, z, 0) - IsoCamera.getOffX(playerIndex),
                        IsoUtils.YToScreen(world.x, world.y, z, 0) - IsoCamera.getOffY(playerIndex));
            }
        }
        Point[] hull = hull(points);
        if (hull.length < 3) return;
        activeHull = hull;
        minX = minY = Float.POSITIVE_INFINITY;
        maxX = maxY = Float.NEGATIVE_INFINITY;
        for (Point point : hull) {
            minX = Math.min(minX, point.x); maxX = Math.max(maxX, point.x);
            minY = Math.min(minY, point.y); maxY = Math.max(maxY, point.y);
        }
        draws++;
        lastPoints = hull.length;
    }

    public static void endParticles() { activeHull = null; }

    public static boolean skipParticle(WeatherParticle particle, float x, float y) {
        if (activeHull == null) return false;
        var bounds = (org.lwjgl.util.Rectangle) PARTICLE_BOUNDS.get(particle);
        return skip(x + bounds.getX(), y + bounds.getY(), bounds.getWidth(), bounds.getHeight());
    }

    /** Suppress a flake/drop whose screen bounds overlap the sheltered cabin.
     * The fast bounds rejection leaves precipitation elsewhere unchanged. Testing
     * the complete particle prevents its edge from bleeding across a cabin wall. */
    public static boolean skip(float x, float y, float width, float height) {
        Point[] hull = activeHull;
        if (hull == null) return false;
        tested++;
        float right = x + width, bottom = y + height;
        if (right < minX || x > maxX || bottom < minY || y > maxY) return false;
        for (int i = 0; i < hull.length; i++) {
            Point a = hull[i], b = hull[(i + 1) % hull.length];
            float dx = b.x - a.x, dy = b.y - a.y;
            // Maximum cross product among the four corners of the particle bounds.
            float px = dx >= 0 ? bottom : y;
            float py = dy >= 0 ? x : right;
            if (dx * (px - a.y) - dy * (py - a.x) < 0) return false;
        }
        sheltered++;
        return true;
    }

    private static Point[] hull(Point[] points) {
        Arrays.sort(points, Comparator.comparingDouble(Point::x).thenComparingDouble(Point::y));
        Point[] result = new Point[points.length * 2];
        int n = 0;
        for (Point p : points) {
            while (n >= 2 && cross(result[n - 2], result[n - 1], p) <= 0) n--;
            result[n++] = p;
        }
        int lower = n;
        for (int i = points.length - 2; i >= 0; i--) {
            Point p = points[i];
            while (n > lower && cross(result[n - 2], result[n - 1], p) <= 0) n--;
            result[n++] = p;
        }
        return Arrays.copyOf(result, Math.max(0, n - 1));
    }

    private static float cross(Point a, Point b, Point c) {
        return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
    }

    public static String info() {
        return "{\"enabled\":" + enabled + ",\"draws\":" + draws + ",\"points\":" + lastPoints
                + ",\"tested\":" + tested + ",\"sheltered\":" + sheltered + ",\"scopes\":" + scopes
                + ",\"roomPoints\":" + (room == null ? 0 : room.ring.length / 2) + "}";
    }
}
