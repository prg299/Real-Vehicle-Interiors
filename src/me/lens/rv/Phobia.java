package me.lens.rv;

import java.util.ArrayDeque;
import java.util.Collections;
import java.util.Deque;
import java.util.Map;
import java.util.WeakHashMap;
import java.util.concurrent.ConcurrentHashMap;
import zombie.GameTime;
import zombie.characters.CharacterStat;
import zombie.characters.IsoGameCharacter;
import zombie.characters.IsoPlayer;
import zombie.characters.traits.CharacterTraits;
import zombie.scripting.objects.CharacterTrait;
import zombie.vehicles.BaseVehicle;
import zombie.scripting.objects.VehicleScript;

/** Replaces the native phobia rates only at their exact trait lookups while a player is
 * in a registered ME: LENS enclosed interior. Stored traits and unrelated panic sources
 * are left alone. */
public final class Phobia {
    private static final float ROOM_THRESHOLD = 70f;
    private static final Map<String, Map<String, Float>> ENCLOSURES = new ConcurrentHashMap<>();
    private static final Map<IsoGameCharacter, Long> SEQUENCES =
            Collections.synchronizedMap(new WeakHashMap<>());
    private static final Map<IsoGameCharacter, Receipt> LAST =
            Collections.synchronizedMap(new WeakHashMap<>());
    private static final ThreadLocal<Deque<Context>> CONTEXTS = new ThreadLocal<>();
    private static final Context OUTSIDE = new Context(null, 0);
    private static final StackWalker WALKER = StackWalker.getInstance(StackWalker.Option.RETAIN_CLASS_REFERENCE);

    private Phobia() {}

    /** Shared seat classification; vision and panic must agree, including remote
     * occupants and furniture seats, without depending on client render state. */
    static boolean isEnclosed(IsoGameCharacter character) {
        BaseVehicle v = character == null ? null : character.getVehicle();
        VehicleScript script = v == null ? null : v.getScript();
        if (script == null) return false;
        Map<String, Float> seats = ENCLOSURES.get(script.getFullName());
        if (seats == null || seats.isEmpty()) return false;
        int seat = v.getSeat(character);
        return seat >= 0 && seat < script.getPassengerCount()
                && seats.containsKey(script.getPassenger(seat).getId());
    }

    /** Called by shared Lua for each mapped passenger position; repeating a registration is safe. */
    public static void registerEnclosure(String scriptName, String passengerId, double roomArea) {
        if (scriptName == null || scriptName.isBlank() || passengerId == null || passengerId.isBlank()
                || !Double.isFinite(roomArea) || roomArea <= 0) {
            return;
        }
        ENCLOSURES.computeIfAbsent(scriptName, ignored -> new ConcurrentHashMap<>())
                .put(passengerId, (float) roomArea);
    }

    /** Advice target: establish a per-player scope around IsoGameCharacter.updateInternal. */
    public static void beginUpdate(IsoGameCharacter character) {
        if (!(character instanceof IsoPlayer)) return;
        Deque<Context> stack = CONTEXTS.get();
        Context context = resolve(character);
        if (context == null) {
            // Ordinary outdoor/cab updates do not allocate scopes or receipts.
            // A nested outside update must still mask an enclosing player's scope.
            if (stack != null && !stack.isEmpty()) stack.push(OUTSIDE);
            return;
        }
        if (stack == null) {
            stack = new ArrayDeque<>();
            CONTEXTS.set(stack);
        }
        stack.push(context);
    }

    /** Advice target: always unwind the per-player scope, including exceptional exits. */
    public static void endUpdate(IsoGameCharacter character) {
        if (!(character instanceof IsoPlayer)) return;
        Deque<Context> stack = CONTEXTS.get();
        if (stack != null && !stack.isEmpty()
                && (stack.peek() == OUTSIDE || stack.peek().character == character)) {
            Context context = stack.pop();
            if (context != OUTSIDE) finish(context);
        }
        // Keep the empty per-thread deque for the next interior update.
    }

    /** Advice target: this is called after CharacterTraits.get returns. */
    public static boolean traitResult(CharacterTraits traits, CharacterTrait trait, boolean value) {
        if (!value || traits == null || trait == null) return value;
        if (trait != CharacterTrait.AGORAPHOBIC && trait != CharacterTrait.CLAUSTROPHOBIC) return value;
        Deque<Context> stack = CONTEXTS.get();
        if (stack == null || stack.isEmpty()) return value;
        Context context = stack.peek();
        if (context == null || !context.inside || context.traits != traits || !nativeTraitCall()) return value;

        if (trait == CharacterTrait.AGORAPHOBIC && !context.agoraphobicHandled) {
            context.agoraphobicHandled = true;
            context.agoraSuppressed = true;
            return false;
        }
        if (trait == CharacterTrait.CLAUSTROPHOBIC && !context.claustrophobicHandled) {
            context.claustrophobicHandled = true;
            context.panicBefore = context.character.getStats().get(CharacterStat.PANIC);
            context.multiplier = GameTime.getInstance().getThirtyFPSMultiplier();
            context.claustroAdded = 0.6f * Math.max(0f, 1f - context.area / ROOM_THRESHOLD)
                    * context.multiplier;
            context.character.getStats().add(CharacterStat.PANIC, context.claustroAdded);
            context.panicAfter = context.character.getStats().get(CharacterStat.PANIC);
            return false;
        }
        return value;
    }

    /** Diagnostics consumed by the in-game multiplayer harness. */
    public static String debugState(IsoGameCharacter character) {
        if (!isEnclosed(character)) return "{}";
        Receipt receipt = LAST.get(character);
        return receipt == null ? "{}" : receipt.json();
    }

    private static Context resolve(IsoGameCharacter character) {
        BaseVehicle vehicle = character.getVehicle();
        if (vehicle == null) return null;
        VehicleScript script = vehicle.getScript();
        if (script == null) return null;
        Map<String, Float> seats = ENCLOSURES.get(script.getFullName());
        if (seats == null || seats.isEmpty()) return null;
        int occupiedSeat = vehicle.getSeat(character);
        if (occupiedSeat < 0 || occupiedSeat >= script.getPassengerCount()) return null;
        String id = script.getPassenger(occupiedSeat).getId();
        Float area = seats.get(id);
        if (area == null || character.getCharacterTraits() == null) return null;
        Context context = new Context(character, nextSequence(character));
        context.traits = character.getCharacterTraits();
        context.inside = true;
        context.profile = script.getFullName();
        context.seat = id;
        context.area = area;
        return context;
    }

    private static long nextSequence(IsoGameCharacter character) {
        synchronized (SEQUENCES) {
            long next = SEQUENCES.getOrDefault(character, 0L) + 1L;
            SEQUENCES.put(character, next);
            return next;
        }
    }

    private static void finish(Context context) {
        LAST.put(context.character, new Receipt(context.sequence, context.profile, context.seat,
                context.inside, context.area, context.agoraSuppressed, context.claustroAdded,
                context.panicBefore, context.panicAfter, context.multiplier));
    }

    /** Require CharacterTraits.get to be called directly by the native update method. */
    private static boolean nativeTraitCall() {
        try {
            return WALKER.walk(frames -> {
                var iterator = frames.iterator();
                while (iterator.hasNext()) {
                    var frame = iterator.next();
                    if (frame.getDeclaringClass() == CharacterTraits.class && frame.getMethodName().equals("get")) {
                        if (!iterator.hasNext()) return false;
                        var caller = iterator.next();
                        return caller.getDeclaringClass() == IsoGameCharacter.class
                                && caller.getMethodName().equals("updateInternal");
                    }
                }
                return false;
            });
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static final class Context {
        final IsoGameCharacter character;
        final long sequence;
        CharacterTraits traits;
        boolean inside;
        String profile = "";
        String seat = "";
        float area;
        boolean agoraphobicHandled;
        boolean claustrophobicHandled;
        boolean agoraSuppressed;
        float claustroAdded;
        float panicBefore = Float.NaN;
        float panicAfter = Float.NaN;
        float multiplier;

        Context(IsoGameCharacter character, long sequence) {
            this.character = character;
            this.sequence = sequence;
        }
    }

    private record Receipt(long sequence, String profile, String seat, boolean inside, float area,
            boolean agoraSuppressed, float claustroAdded, float panicBefore, float panicAfter,
            float multiplier) {
        String json() {
            return "{\"sequence\":" + sequence + ",\"inside\":" + inside + ",\"profile\":"
                    + string(profile) + ",\"seat\":" + string(seat) + ",\"area\":" + number(area)
                    + ",\"agoraSuppressed\":" + agoraSuppressed + ",\"claustroAdded\":" + number(claustroAdded)
                    + ",\"panicAtLookupBefore\":" + number(panicBefore)
                    + ",\"panicAtLookupAfter\":" + number(panicAfter)
                    + ",\"multiplier\":" + number(multiplier) + "}";
        }

        private static String string(String value) {
            return value == null || value.isEmpty() ? "null" : "\"" + escape(value) + "\"";
        }

        private static String number(float value) {
            return Float.isFinite(value) ? Float.toString(value) : "null";
        }

        private static String escape(String value) {
            return value.replace("\\", "\\\\").replace("\"", "\\\"");
        }
    }
}
