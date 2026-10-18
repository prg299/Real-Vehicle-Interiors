package me.lens.dev;

import java.util.ArrayDeque;
import me.zed_0xff.zombie_buddy.Exposer;
import me.zed_0xff.zombie_buddy.Patch;
import zombie.core.Core;
import zombie.input.GameKeyboard;
import zombie.ui.UITextEntryInterface;

/** Isolated developer profile only. Feeds the native text event queue, not widgets. */
@Exposer.LuaClass(name = "MELensNativeText")
public final class TextInput {
    private static final int LIMIT = 512;
    private static final long GAP_NS = 35_000_000L;
    private static final long TTL_NS = 25_000_000_000L;
    private static final ArrayDeque<Event> pending = new ArrayDeque<>();
    private static UITextEntryInterface target;
    private static long nextAt, deadline, sent;
    private static String failure = "";

    private record Event(char character, int glfwKey) {}
    private TextInput() {}

    private static void admit(int count) {
        UITextEntryInterface focused = Core.currentTextEntryBox;
        if (focused == null || !focused.isDoingTextEntry() || !focused.isEditable())
            throw new IllegalStateException("Click a native text entry before queuing input");
        if (!pending.isEmpty() && target != focused)
            throw new IllegalStateException("An earlier text entry still owns queued input");
        if (count < 0 || pending.size() + count > LIMIT)
            throw new IllegalArgumentException("Native text queue limit is " + LIMIT + " events");
        if (pending.isEmpty()) {
            target = focused;
            failure = "";
            nextAt = System.nanoTime() + GAP_NS;
        }
        deadline = System.nanoTime() + TTL_NS;
    }

    /** Printable BMP text only; tests deliberately use ASCII for NAME_MAX byte parity. */
    public static synchronized void text(String text) {
        if (text == null || text.length() > 256) throw new IllegalArgumentException("text length 0..256");
        for (char c : text.toCharArray())
            if (Character.isISOControl(c) || Character.isSurrogate(c))
                throw new IllegalArgumentException("Printable BMP text required");
        admit(text.length());
        for (char c : text.toCharArray()) pending.addLast(new Event(c, 0));
    }

    /** Native editing keys, using GLFW key codes expected by KeyEventQueue.addKeyEvent. */
    public static synchronized void key(String name, int count) {
        int glfw = switch (name) {
            case "BACKSPACE" -> 259;
            case "DELETE" -> 261;
            case "HOME" -> 268;
            case "END" -> 269;
            default -> throw new IllegalArgumentException("BACKSPACE, DELETE, HOME or END");
        };
        if (count < 1 || count > 256) throw new IllegalArgumentException("key count 1..256");
        admit(count);
        for (int i = 0; i < count; i++) pending.addLast(new Event('\0', glfw));
    }

    public static synchronized int queued() { return pending.size(); }
    public static synchronized long sent() { return sent; }
    public static synchronized String failure() { return failure; }
    public static synchronized void cancel() { pending.clear(); target = null; }

    public static synchronized void pump() {
        if (pending.isEmpty()) return;
        long now = System.nanoTime();
        if (now > deadline || Core.currentTextEntryBox != target
                || !target.isDoingTextEntry() || !target.isEditable()) {
            failure = now > deadline ? "queued input expired" : "text entry lost focus";
            cancel();
            return;
        }
        if (now < nextAt) return;
        // Ignore-first is the engine's ordinary focus transition. Let its next
        // update clear the flag before feeding a character that would be dropped.
        if (target.isIgnoreFirst()) return;
        Event event = pending.removeFirst();
        var queue = GameKeyboard.getEventQueue();
        if (event.glfwKey() == 0) queue.addCharEvent(event.character());
        else {
            queue.addKeyEvent(event.glfwKey(), 1);
            queue.addKeyEvent(event.glfwKey(), 0);
        }
        sent++;
        nextAt = now + GAP_NS;
        if (pending.isEmpty()) target = null;
    }

    @Patch(className = "zombie.core.Core", methodName = "updateKeyboard", strictMatch = true)
    public static final class NativeTextDispatch {
        @Patch.OnEnter public static void enter() { TextInput.pump(); }
    }
}
