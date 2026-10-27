package me.lens.dev;

import me.zed_0xff.zombie_buddy.Exposer;
import zombie.GameWindow;
import zombie.gameStates.GameLoadingState;
import java.lang.reflect.Field;
import java.nio.ByteBuffer;
import java.nio.file.Path;
import java.nio.file.Files;
import java.awt.image.BufferedImage;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import me.zed_0xff.zombie_buddy.Patch;
import static org.lwjgl.opengl.GL11.*;
import static org.lwjgl.opengl.GL15.*;
import static org.lwjgl.opengl.GL21.*;
import static org.lwjgl.opengl.GL30.*;

/** Isolated media-profile setup only. Never included in the shipping mod. */
@Exposer.LuaClass(name = "MELensMedia")
public final class Media {
    private Media() {}

    private record Camera(float x, float y, float z, float previousPanX, float previousPanY) { }
    private static volatile Camera fixedCamera;
    private static volatile boolean nativePan;
    private static final Field cameraGoalX = cameraGoal("tOffX");
    private static final Field cameraGoalY = cameraGoal("tOffY");

    private static Field cameraGoal(String name) {
        try {
            Field field = zombie.iso.PlayerCamera.class.getDeclaredField(name);
            field.setAccessible(true);
            return field;
        } catch (ReflectiveOperationException error) {
            throw new ExceptionInInitializerError(error);
        }
    }

    /** Capture framing fixture only; input checks run with the ordinary camera. */
    public static void camera(float x, float y, float z) {
        Camera previous = fixedCamera;
        var camera = zombie.iso.IsoCamera.cameras[0];
        fixedCamera = new Camera(x, y, z, previous == null ? camera.deferedX : previous.previousPanX,
            previous == null ? camera.deferedY : previous.previousPanY);
    }
    public static void cameraOff() {
        Camera previous = fixedCamera;
        fixedCamera = null;
        if (previous != null) {
            var camera = zombie.iso.IsoCamera.cameras[0];
            camera.deferedX = previous.previousPanX; camera.deferedY = previous.previousPanY;
        }
    }

    /** Diagnostic switch: preserve the legacy offset path for same-pose controls. */
    public static void cameraNativePan(boolean enabled) {
        Camera target = fixedCamera;
        if (target != null) {
            var camera = zombie.iso.IsoCamera.cameras[0];
            camera.deferedX = target.previousPanX; camera.deferedY = target.previousPanY;
        }
        nativePan = enabled;
    }

    // center() also runs independently of update(). Keep both interpolation
    // endpoints on the requested target instead of drifting back to the player.
    @Patch(className = "zombie.iso.PlayerCamera", methodName = "center")
    public static final class CaptureCamera {
        @Patch.OnEnter public static void enter() { Media.panCamera(); }
        @Patch.OnExit public static void exit() { Media.offsetCamera(); }
    }

    public static void frameCamera() {
        if (fixedCamera == null) return;
        if (nativePan) zombie.iso.IsoCamera.cameras[0].center();
        else offsetCamera();
    }

    /** Native center/MVP share deferedX/Y; direct 2D offsets alone do not pan the 3D origin. */
    public static void panCamera() {
        Camera target = fixedCamera;
        if (target == null || !nativePan) return;
        var character = zombie.iso.IsoCamera.getCameraCharacter();
        if (character == null) return;
        var camera = zombie.iso.IsoCamera.cameras[0];
        float z = zombie.iso.IsoCamera.frameState.calculateCameraZ(character);
        float sx = zombie.iso.IsoUtils.XToScreen(target.x, target.y, target.z, 0)
            - zombie.iso.IsoCamera.playerOffsetX;
        float sy = zombie.iso.IsoUtils.YToScreen(target.x, target.y, target.z, 0)
            + character.getOffsetY() * 1.5f - zombie.iso.IsoCamera.playerOffsetY;
        float scale = 64f * zombie.core.Core.tileScale;
        camera.deferedX = (sx + 2f * sy) / scale + 3f * z - character.getX();
        camera.deferedY = (sx - 2f * sy) / -scale + 3f * z - character.getY();
        camera.rightClickX = 0; camera.rightClickY = 0;
    }

    public static void offsetCamera() {
        Camera target = fixedCamera;
        if (target == null || nativePan) return;
        var camera = zombie.iso.IsoCamera.cameras[0];
        camera.offX = zombie.iso.IsoUtils.XToScreen(target.x, target.y, target.z, 0)
            - zombie.iso.IsoCamera.getOffscreenWidth(0) / 2f;
        camera.offY = zombie.iso.IsoUtils.YToScreen(target.x, target.y, target.z, 0)
            - zombie.iso.IsoCamera.getOffscreenHeight(0) / 2f;
        camera.lastOffX = camera.offX; camera.lastOffY = camera.offY;
        try {
            cameraGoalX.setFloat(camera, camera.offX);
            cameraGoalY.setFloat(camera, camera.offY);
        } catch (IllegalAccessException error) {
            throw new IllegalStateException("Capture camera target inaccessible", error);
        }
        camera.rightClickX = 0; camera.rightClickY = 0;
    }

    public static String cameraInfo() {
        var camera = zombie.iso.IsoCamera.cameras[0];
        var frame = zombie.iso.IsoCamera.frameState;
        return "nativePan=" + nativePan + ";target=" + fixedCamera + ";buffer=" + zombie.iso.IsoCamera.getOffscreenWidth(0)
            + "x" + zombie.iso.IsoCamera.getOffscreenHeight(0) + ";off=" + camera.offX + "," + camera.offY
            + ";pan=" + camera.deferedX + "," + camera.deferedY
            + ";frameOff=" + frame.offX + "," + frame.offY
            + ";frameCharacter=" + frame.camCharacterX + "," + frame.camCharacterY + "," + frame.camCharacterZ
            + ";zoom=" + zombie.core.Core.getInstance().getZoom(0);
    }

    /** Skip the loading-screen click without interacting with the owner's desktop. */
    public static boolean start() throws ReflectiveOperationException {
        if (!(GameWindow.states.current instanceof GameLoadingState loading)) return false;
        Field field = GameLoadingState.class.getDeclaredField("forceDone");
        field.setAccessible(true);
        field.setBoolean(loading, true);
        return true;
    }

    private static final ThreadPoolExecutor writer = new ThreadPoolExecutor(1, 1, 0, TimeUnit.SECONDS,
        new ArrayBlockingQueue<>(2), runnable -> { var t = new Thread(runnable, "LENS-media-writer"); t.setDaemon(true); return t; });
    private static volatile Path directory;
    private static volatile long endAt;
    private static long nextAt, startedAt;
    private static int index;
    private static ByteBuffer pixels;
    private static final int WIDTH = 1280, HEIGHT = 720;

    /** Bounded recording: one reused direct buffer, at most two queued frames, 15 FPS. */
    public static synchronized void clip(String name, int seconds) throws java.io.IOException {
        if (!name.matches("clip-[a-z0-9-]+") || seconds < 1 || seconds > 30) throw new IllegalArgumentException();
        if (System.nanoTime() < endAt || !writer.getQueue().isEmpty()) throw new IllegalStateException("recording/writer busy");
        Path target = Path.of(zombie.ZomboidFileSystem.instance.getScreenshotDir(), name);
        Files.createDirectory(target);
        directory = target;
        index = 0;
        startedAt = System.nanoTime(); nextAt = startedAt;
        endAt = startedAt + seconds * 1_000_000_000L;
    }

    public static void frame() {
        long now = System.nanoTime();
        if (now >= endAt || now < nextAt || writer.getQueue().remainingCapacity() == 0) return;
        nextAt = now + 66_666_667L;
        if (pixels == null) pixels = org.lwjgl.BufferUtils.createByteBuffer(WIDTH * HEIGHT * 4);
        pixels.clear();
        int fbo = glGetInteger(GL_READ_FRAMEBUFFER_BINDING), buffer = glGetInteger(GL_READ_BUFFER);
        int pack = glGetInteger(GL_PIXEL_PACK_BUFFER_BINDING), align = glGetInteger(GL_PACK_ALIGNMENT);
        try {
            glBindFramebuffer(GL_READ_FRAMEBUFFER, 0); glReadBuffer(GL_BACK);
            glBindBuffer(GL_PIXEL_PACK_BUFFER, 0); glPixelStorei(GL_PACK_ALIGNMENT, 1);
            glReadPixels(0, 0, WIDTH, HEIGHT, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
        } finally {
            glBindFramebuffer(GL_READ_FRAMEBUFFER, fbo); glReadBuffer(buffer);
            glBindBuffer(GL_PIXEL_PACK_BUFFER, pack); glPixelStorei(GL_PACK_ALIGNMENT, align);
        }
        int[] rgb = new int[WIDTH * HEIGHT];
        for (int row = 0; row < HEIGHT; row++) for (int col = 0; col < WIDTH; col++) {
            int i = ((HEIGHT - row - 1) * WIDTH + col) * 4;
            rgb[row * WIDTH + col] = (pixels.get(i) & 255) << 16 | (pixels.get(i + 1) & 255) << 8 | (pixels.get(i + 2) & 255);
        }
        final Path path = directory; final int number = index++;
        final double seconds = (now - startedAt) / 1_000_000_000.0;
        writer.execute(() -> {
            var image = new BufferedImage(WIDTH, HEIGHT, BufferedImage.TYPE_INT_RGB);
            image.setRGB(0, 0, WIDTH, HEIGHT, rgb, 0, WIDTH);
            String name = String.format("f%05d.jpg", number);
            try {
                var jpeg = javax.imageio.ImageIO.getImageWritersByFormatName("jpeg").next();
                try (var output = javax.imageio.ImageIO.createImageOutputStream(path.resolve(name).toFile())) {
                    jpeg.setOutput(output); var options = jpeg.getDefaultWriteParam();
                    options.setCompressionMode(javax.imageio.ImageWriteParam.MODE_EXPLICIT);
                    options.setCompressionQuality(.96f);
                    jpeg.write(null, new javax.imageio.IIOImage(image, null, null), options);
                } finally { jpeg.dispose(); }
                Files.writeString(path.resolve("frames.csv"), name + "," + seconds + "\n",
                    java.nio.file.StandardOpenOption.CREATE, java.nio.file.StandardOpenOption.APPEND);
            } catch (java.io.IOException error) { throw new java.io.UncheckedIOException(error); }
        });
    }

    /** Read-only diagnostics for loaded furniture assets; never loads or changes a model. */
    public static String furnitureBounds(String name) {
        if (name == null || !name.matches("MELensRV_[a-z0-9_]+")) throw new IllegalArgumentException();
        var script = zombie.scripting.ScriptManager.instance.getModelScript(name);
        if (script == null) return name + " script missing";
        var model = zombie.core.skinnedmodel.ModelManager.instance.tryGetLoadedModel(script.getMeshName(),
            script.getTextureName(), script.isStatic, script.getShaderName(), false);
        String info = name + " scale=" + script.scale + " shader=" + script.getShaderName();
        if (model == null || !model.isReady() || model.mesh == null || !model.mesh.isReady()) {
            return info + " model not loaded";
        }
        var transform = new org.joml.Matrix4f();
        var attachment = script.getAttachmentById("world");
        if (attachment != null) {
            var world = new org.joml.Matrix4f();
            zombie.core.skinnedmodel.model.ModelInstanceRenderData.makeAttachmentTransform(attachment, world);
            transform.mul(world.invert());
        }
        zombie.core.skinnedmodel.model.ModelInstanceRenderData.postMultiplyMeshTransform(transform, model.mesh);
        transform.scale(script.scale * 1.5f);
        var lo = new org.joml.Vector3f(Float.POSITIVE_INFINITY);
        var hi = new org.joml.Vector3f(Float.NEGATIVE_INFINITY);
        var corner = new org.joml.Vector3f();
        var min = model.mesh.minXyz;
        var max = model.mesh.maxXyz;
        for (int i = 0; i < 8; i++) {
            corner.set((i & 1) == 0 ? min.x : max.x, (i & 2) == 0 ? min.y : max.y,
                (i & 4) == 0 ? min.z : max.z);
            transform.transformPosition(corner);
            lo.min(corner); hi.max(corner);
        }
        return info + " itemCameraBounds=" + lo + ".." + hi + " size=" + new org.joml.Vector3f(hi).sub(lo)
            + " meshBounds=" + min + ".." + max + " meshTransform=" + model.mesh.transform;
    }

    @Patch(className = "org.lwjglx.opengl.Display", methodName = "swapBuffers")
    public static final class Frames {
        @Patch.OnEnter public static void enter() { Media.frame(); }
    }
}
