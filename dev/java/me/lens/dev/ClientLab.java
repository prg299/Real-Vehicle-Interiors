package me.lens.dev;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.concurrent.ConcurrentHashMap;
import me.zed_0xff.zombie_buddy.Exposer;
import me.zed_0xff.zombie_buddy.Patch;
import zombie.input.KeyboardState;
import static org.lwjgl.opengl.GL11.*;
import static org.lwjgl.opengl.GL15.*;
import static org.lwjgl.opengl.GL21.*;
import static org.lwjgl.opengl.GL30.*;

/** Test-only keyboard/mouse queues, weather controls and completed-frame capture. */
@Exposer.LuaClass(name="MEMCNativeLab")
public final class ClientLab {
    /** Read actual part-model bindings. No render/cache or inventory mutation. */
    public static String interiorModels(zombie.vehicles.BaseVehicle vehicle) {
        var out = new StringBuilder("[");
        for (var model : vehicle.models) {
            if (model.part == null || model.scriptModel == null) continue;
            String id = model.part.getId();
            if (!id.equals("MELensShell") && !id.startsWith("MELensSpot")) continue;
            if (out.length() > 1) out.append(',');
            out.append("{\"part\":\"").append(id).append("\",\"model\":\"")
                .append(model.scriptModel.id).append("\",\"live\":")
                .append(vehicle.getPartById(id) == model.part).append('}');
        }
        return out.append(']').toString();
    }
    /** Explicit model-loss fixture; leaves live parts, inventories and Lua caches untouched. */
    public static int dropInteriorModels(zombie.vehicles.BaseVehicle vehicle) {
        int count = 0;
        for (var model : new ArrayList<>(vehicle.models)) {
            if (model.part == null || model.scriptModel == null) continue;
            String id = model.part.getId();
            if (id.equals("MELensShell") || id.startsWith("MELensSpot")) {
                vehicle.setModelVisible(model.part, model.scriptModel, false);
                count++;
            }
        }
        return count;
    }
    public static final ConcurrentHashMap<Integer,Long> keys = new ConcurrentHashMap<>();
    public static final Field keyboardStates;
    public static final Field mouseStates;
    public static final Field mouseX,mouseY,mouseWheel;
    public static volatile long mouseStarts,mouseUntil;
    public static volatile int mouseButton;
    public static volatile boolean mouseOverride;
    public static volatile boolean keyboardOverride;
    public static volatile int pointerX=640,pointerY=360;
    public static boolean nativeMouseDown;
    public static int nativeMouseButton,nativeMouseX=-1,nativeMouseY=-1;
    static {
        try { keyboardStates=KeyboardState.class.getDeclaredField("keyDownStates"); keyboardStates.setAccessible(true);
            mouseStates=zombie.input.MouseState.class.getDeclaredField("buttonDownStates");mouseStates.setAccessible(true);
            mouseX=zombie.input.MouseState.class.getDeclaredField("mouseX");mouseX.setAccessible(true);
            mouseY=zombie.input.MouseState.class.getDeclaredField("mouseY");mouseY.setAccessible(true);
            mouseWheel=zombie.input.MouseState.class.getDeclaredField("wheelDelta");mouseWheel.setAccessible(true); }
        catch(Exception e) { throw new ExceptionInInitializerError(e); }
    }
    public static void holdKey(int key, int milliseconds) {
        if(key<0 || key>=256 || milliseconds<0 || milliseconds>10000) throw new IllegalArgumentException();
        keyboardOverride=true;
        keys.put(key,System.nanoTime()+milliseconds*1000000L);
    }
    public static void releaseKeys() { keyboardOverride=true; keys.replaceAll((k,v)->0L); }
    /** Read native bone transforms without installing any model/render probes. */
    public static String animationBones() {
        var p = zombie.characters.IsoPlayer.getInstance();
        if (p == null || p.getAnimationPlayer() == null) return "none";
        var ap = p.getAnimationPlayer();
        var out = new StringBuilder();
        for (String name : new String[]{"Bip01_Pelvis", "Bip01_Head", "Bip01_L_Foot", "Bip01_R_Foot"}) {
            int index = ap.getSkinningBoneIndex(name, -1);
            if (index < 0) continue;
            var matrix = ap.getModelTransformAt(index);
            out.append(name).append(':').append(matrix.m03).append(',').append(matrix.m13).append(',')
                .append(matrix.m23).append(';');
        }
        return out.toString();
    }
    /** Same native scene/weather with only the cabin mask disabled, for A/B evidence. */
    public static void weatherMask(boolean enabled) throws Exception {
        Field field=Class.forName("me.lens.rv.Weather").getDeclaredField("enabled");
        field.setAccessible(true); field.setBoolean(null,enabled);
    }
    /** Same native perception inputs with only the additive cabin LOS disabled. */
    public static void visionMask(boolean enabled) throws Exception {
        Field field=Class.forName("me.lens.rv.Vision").getDeclaredField("enabled");
        field.setAccessible(true); field.setBoolean(null,enabled);
    }
    public static void forceSpot(zombie.characters.IsoZombie observer, zombie.characters.IsoPlayer target, boolean old) {
        if(old) observer.spottedOld(target,true); else observer.spottedNew(target,true);
    }
    public static String zombieInfo(zombie.characters.IsoZombie z, zombie.characters.IsoPlayer p) {
        return "{\"targetPlayer\":"+(z.getTarget()==p)+",\"targetNull\":"+(z.getTarget()==null)
            +",\"seenSince\":"+z.timeSinceSeenFlesh+",\"seenX\":"+z.lastTargetSeenX+",\"seenY\":"+z.lastTargetSeenY
            +",\"heardPlayer\":"+(z.soundSourceTarget==p)+",\"soundSince\":"+z.timeSinceRespondToSound
            +",\"goalSound\":"+z.getPathFindBehavior2().isGoalSound()+",\"state\":\""
            +(z.getCurrentState()==null?"":z.getCurrentState().getClass().getSimpleName())+"\"}";
    }
    public static volatile boolean frozenWeather;
    public static void freezeWeather(boolean frozen) { frozenWeather=frozen; }
    @Patch(className="zombie.iso.weather.fx.IsoWeatherFX",methodName="update",strictMatch=true)
    public static final class FreezeWeather {
        @Patch.OnEnter(skipOn=true) public static boolean enter() { return frozenWeather; }
    }
    public static void clickAt(int x,int y) {
        clickButtonAt(x,y,0);
    }
    public static void clickButtonAt(int x,int y,int button) {
        if(x<0 || y<0 || x>=1280 || y>=720)throw new IllegalArgumentException();
        if(button<0 || button>2)throw new IllegalArgumentException();
        mouseButton=button;
        pointerX=x;pointerY=y;mouseOverride=true;
        // Let the native hover/picker update before pressing at the new position.
        // UIManager processes button transitions before refreshing the picked tile.
        mouseStarts=System.nanoTime()+150000000L;
        mouseUntil=mouseStarts+(button==1?70000000L:300000000L);
    }
    public static void clickToStart() {clickAt(640,360);}
    private static final java.util.concurrent.atomic.AtomicReference<String> pendingCapture = new java.util.concurrent.atomic.AtomicReference<>();
    /** Queue one raw completed frame; never sample the compositor-owned front buffer. */
    public static void capture(String name) {
        if(!name.matches("[a-z0-9-]+\\.png"))throw new IllegalArgumentException("capture filename");
        if(!pendingCapture.compareAndSet(null,name))throw new IllegalStateException("capture already pending");
    }
    public static void captureBeforeSwap() {
        String name=pendingCapture.getAndSet(null);
        if(name==null)return;
            int fbo=glGetInteger(GL_READ_FRAMEBUFFER_BINDING),buffer=glGetInteger(GL_READ_BUFFER);
            int pack=glGetInteger(GL_PIXEL_PACK_BUFFER_BINDING),align=glGetInteger(GL_PACK_ALIGNMENT);
            int row=glGetInteger(GL_PACK_ROW_LENGTH),skipRows=glGetInteger(GL_PACK_SKIP_ROWS),skipPixels=glGetInteger(GL_PACK_SKIP_PIXELS);
            while(glGetError()!=GL_NO_ERROR){}
            var mode=org.lwjglx.opengl.Display.getDisplayMode();
            try(var pixels=zombie.core.utils.NativeImage.allocate(mode.getWidth(),mode.getHeight())) {
                glBindFramebuffer(GL_READ_FRAMEBUFFER,0);glReadBuffer(GL_BACK);
                glBindBuffer(GL_PIXEL_PACK_BUFFER,0);
                glPixelStorei(GL_PACK_ALIGNMENT,1);glPixelStorei(GL_PACK_ROW_LENGTH,0);
                glPixelStorei(GL_PACK_SKIP_ROWS,0);glPixelStorei(GL_PACK_SKIP_PIXELS,0);
                glReadPixels(0,0,mode.getWidth(),mode.getHeight(),GL_RGBA,GL_UNSIGNED_BYTE,pixels.pixels());
                int error=glGetError();
                if(error!=GL_NO_ERROR)throw new IllegalStateException("native capture GL error="+error);
                var file=new java.io.File(zombie.ZomboidFileSystem.instance.getScreenshotDir(),name);
                if(!pixels.writePng(file.getAbsolutePath(),true))throw new IllegalStateException("PNG write failed");
                System.out.println("[RVI_LAB] native capture "+name+" phase=before-swap buffer=GL_BACK priorReadFbo="+fbo+" priorPackBuffer="+pack+" error="+error);
            } finally {
                glBindFramebuffer(GL_READ_FRAMEBUFFER,fbo);glReadBuffer(buffer);
                glBindBuffer(GL_PIXEL_PACK_BUFFER,pack);glPixelStorei(GL_PACK_ALIGNMENT,align);
                glPixelStorei(GL_PACK_ROW_LENGTH,row);glPixelStorei(GL_PACK_SKIP_ROWS,skipRows);glPixelStorei(GL_PACK_SKIP_PIXELS,skipPixels);
            }
    }
    public static synchronized void mouse(zombie.input.MouseState state) throws Exception {
        if(mouseOverride){long now=System.nanoTime();boolean down=now>=mouseStarts && now<mouseUntil;
            // GLFW's public event queue is the production UI dispatch source.
            // Polled button state alone proves aim/fire, not a context-menu click.
            if(pointerX!=nativeMouseX || pointerY!=nativeMouseY){
                org.lwjglx.input.Mouse.addMoveEvent(pointerX,pointerY);
                nativeMouseX=pointerX;nativeMouseY=pointerY;
            }
            if(down!=nativeMouseDown || mouseButton!=nativeMouseButton){
                if(nativeMouseDown)org.lwjglx.input.Mouse.addButtonEvent(nativeMouseButton,false);
                if(down)org.lwjglx.input.Mouse.addButtonEvent(mouseButton,true);
                nativeMouseDown=down;nativeMouseButton=mouseButton;
            }
            boolean[] b=(boolean[])mouseStates.get(state);Arrays.fill(b,false);if(b.length>mouseButton)b[mouseButton]=down;
            // Internal polling state only; never move the user's OS cursor.
            mouseX.setInt(state,pointerX);mouseY.setInt(state,719-pointerY);mouseWheel.setInt(state,0);}
    }
    public static void poll(KeyboardState state) throws Exception {
        if(!keyboardOverride)return;
        boolean[] values=(boolean[])keyboardStates.get(state);
        Arrays.fill(values,false);
        long now=System.nanoTime();
        keys.forEach((key,until)->{if(key<values.length) values[key]=now<until;});
    }
    private static final ArrayList<Double> frameMs = new ArrayList<>();
    private static long previous;
    private static int remaining;
    public static synchronized void measure(int frames) {frameMs.clear();previous=0;remaining=frames;}
    public static synchronized void frame() {
        if(remaining<=0) return;
        long now=System.nanoTime();
        if(previous!=0){frameMs.add((now-previous)/1e6);remaining--;}
        previous=now;
    }
    public static synchronized String measurement() {
        double[] ms=frameMs.stream().mapToDouble(Double::doubleValue).sorted().toArray();
        if(ms.length==0) return "{\"frames\":0,\"remaining\":"+remaining+"}";
        double mean=Arrays.stream(ms).average().orElse(0);
        return "{\"frames\":"+ms.length+",\"remaining\":"+remaining+",\"meanMs\":"+mean+",\"fps\":"+(1000/mean)+",\"p50Ms\":"+ms[(int)((ms.length-1)*.50)]+",\"p95Ms\":"+ms[(int)((ms.length-1)*.95)]+",\"p99Ms\":"+ms[(int)((ms.length-1)*.99)]+",\"maxMs\":"+ms[ms.length-1]+"}";
    }
    @Patch(className="zombie.input.KeyboardState", methodName="poll")
    public static final class Input {
        @Patch.OnExit public static void exit(@Patch.This KeyboardState state) throws Exception { ClientLab.poll(state); }
    }
    // PZ Optimization can repoll between ordinary polling and input dispatch.
    // Inject at that same input boundary as well; never alter game handlers.
    @Patch(className="zombie.input.KeyboardState", methodName="pzoptRepoll")
    public static final class KeyboardRepoll {
        @Patch.OnExit public static void exit(@Patch.This KeyboardState state) throws Exception {ClientLab.poll(state);}
    }
    @Patch(className="zombie.input.MouseState", methodName="pzoptRepoll")
    public static final class MouseRepoll {
        @Patch.OnExit public static void exit(@Patch.This zombie.input.MouseState state) throws Exception {ClientLab.mouse(state);}
    }
    @Patch(className="zombie.input.MouseState", methodName="poll")
    public static final class MouseInput {
        @Patch.OnExit public static void exit(@Patch.This zombie.input.MouseState state) throws Exception { ClientLab.mouse(state); }
    }
    @Patch(className="zombie.GameWindow", methodName="frameStep")
    public static final class Frames {
        @Patch.OnExit public static void exit() { ClientLab.frame(); }
    }
    @Patch(className="org.lwjglx.opengl.Display", methodName="swapBuffers")
    public static final class CaptureFrame {
        @Patch.OnEnter public static void enter() { ClientLab.captureBeforeSwap(); }
    }
}
