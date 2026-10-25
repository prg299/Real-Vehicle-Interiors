package me.lens.rv;

import java.util.ArrayDeque;
import java.util.Deque;
import zombie.inventory.ItemContainer;
import zombie.inventory.types.Food;
import zombie.iso.IsoGridSquare;
import zombie.vehicles.BaseVehicle;
import zombie.vehicles.VehiclePart;

/** Supply the native food-aging contract for vehicle appliances, without
 * electrifying the world square or replacing the game's food-aging routine. */
public final class Refrigeration {
    private record Context(boolean appliance, IsoGridSquare square, boolean powered) {}
    private static final Context NONE = new Context(false, null, false);
    private static final ThreadLocal<Deque<Context>> CONTEXTS = new ThreadLocal<>();
    private Refrigeration() {}

    public static boolean appliance(ItemContainer container) {
        VehiclePart part = container == null ? null : container.getVehiclePart();
        return part != null && part.getId().startsWith("MELensSpot")
                && part.getInventoryItem() != null
                && "Base.MELensRV_Fridge".equals(part.getInventoryItem().getFullType());
    }

    public static boolean powered(ItemContainer container) {
        if (!appliance(container)) return false;
        BaseVehicle vehicle = container.getVehiclePart().getVehicle();
        if (vehicle == null) return false;
        VehiclePart generator = vehicle.getPartById("MELensGenerator");
        if (generator != null && generator.getCondition() > 0
                && Boolean.TRUE.equals(generator.getModData().rawget("on"))) {
            Object fuel = generator.getModData().rawget("fuel");
            if (fuel instanceof Number amount && amount.doubleValue() > 0) return true;
        }
        return Boolean.TRUE.equals(vehicle.getModData().rawget("MELensShore"));
    }

    public static IsoGridSquare square(ItemContainer container) {
        BaseVehicle vehicle = container.getVehiclePart().getVehicle();
        return vehicle == null ? null : vehicle.getSquare();
    }

    public static void begin(Food food) {
        ItemContainer container = food.getOutermostContainer();
        boolean appliance = appliance(container);
        Deque<Context> stack = CONTEXTS.get();
        if (stack == null) { stack = new ArrayDeque<>(); CONTEXTS.set(stack); }
        stack.push(appliance ? new Context(true, square(container), powered(container)) : NONE);
    }

    public static void end() {
        Deque<Context> stack = CONTEXTS.get();
        if (stack == null) return;
        stack.pop();
    }

    public static boolean electricity(IsoGridSquare square, boolean vanilla) {
        Deque<Context> stack = CONTEXTS.get();
        Context context = stack == null ? null : stack.peek();
        return context != null && context.appliance && context.square == square
                ? context.powered : vanilla;
    }
}
