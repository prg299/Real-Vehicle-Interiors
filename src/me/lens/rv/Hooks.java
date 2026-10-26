package me.lens.rv;

import me.zed_0xff.zombie_buddy.Patch;
import zombie.characters.IsoPlayer;
import zombie.characters.IsoGameCharacter;
import zombie.characters.traits.CharacterTraits;
import zombie.characters.action.ActionGroup;
import zombie.scripting.objects.CharacterTrait;
import zombie.core.skinnedmodel.model.Model;
import zombie.core.skinnedmodel.model.ModelInstanceRenderData;
import zombie.core.skinnedmodel.model.ModelSlotRenderData;
import zombie.iso.IsoObject;
import zombie.vehicles.BaseVehicle;

/**
 * Engine hooks. The render hooks do nothing unless Lua armed them; the animation-set hooks
 * only act for characters Lua marked as standing in a camper (see {@link Standing}).
 */
public final class Hooks {
    private Hooks() {}

    /** Retired animal drawers may finish after the last vehicle draw, including
     * while returning to the menu. Release their animation players on the main
     * thread once the render thread has finished all queued states. */
    @Patch(className = "zombie.GameWindow", methodName = "frameStep", strictMatch = true)
    public static final class RetiredAnimalModels {
        @Patch.OnExit
        public static void exit() { Animals.releaseRetired(); }
    }

    @Patch(className = "zombie.inventory.ItemContainer", methodName = "isFridge", strictMatch = true)
    public static final class InteriorFridgeType {
        @Patch.OnExit
        public static void exit(@Patch.This zombie.inventory.ItemContainer container,
                @Patch.Return(readOnly = false) boolean fridge) {
            if (Refrigeration.appliance(container)) fridge = Refrigeration.powered(container);
        }
    }

    @Patch(className = "zombie.inventory.ItemContainer", methodName = "isPowered", strictMatch = true)
    public static final class InteriorFridgePower {
        @Patch.OnExit
        public static void exit(@Patch.This zombie.inventory.ItemContainer container,
                @Patch.Return(readOnly = false) boolean powered) {
            if (Refrigeration.appliance(container)) powered = Refrigeration.powered(container);
        }
    }

    @Patch(className = "zombie.inventory.ItemContainer", methodName = "getTemperature", strictMatch = true)
    public static final class InteriorFridgeTemperature {
        @Patch.OnExit
        public static void exit(@Patch.This zombie.inventory.ItemContainer container,
                @Patch.Return(readOnly = false) float temperature) {
            if (Refrigeration.appliance(container)) temperature = Refrigeration.powered(container) ? 0.2f : 1f;
        }
    }

    @Patch(className = "zombie.inventory.ItemContainer", methodName = "getSourceGrid", strictMatch = true)
    public static final class InteriorFridgeSquare {
        @Patch.OnExit
        public static void exit(@Patch.This zombie.inventory.ItemContainer container,
                @Patch.Return(readOnly = false) zombie.iso.IsoGridSquare square) {
            if (Refrigeration.appliance(container)) square = Refrigeration.square(container);
        }
    }

    @Patch(className = "zombie.inventory.types.Food", methodName = "updateAge", strictMatch = true)
    public static final class InteriorFoodAge {
        @Patch.OnEnter
        public static void enter(@Patch.This zombie.inventory.types.Food food,
                @Patch.Argument(0) boolean force) { Refrigeration.begin(food); }
        @Patch.OnExit(onThrowable = Throwable.class)
        public static void exit(@Patch.Argument(0) boolean force) { Refrigeration.end(); }
    }

    @Patch(className = "zombie.iso.IsoGridSquare", methodName = "haveElectricity", strictMatch = true)
    public static final class InteriorFoodElectricity {
        @Patch.OnExit
        public static void exit(@Patch.This zombie.iso.IsoGridSquare square,
                @Patch.Return(readOnly = false) boolean powered) {
            powered = Refrigeration.electricity(square, powered);
        }
    }

    @Patch(className = "zombie.characters.IsoZombie", methodName = "spottedNew", strictMatch = true)
    public static final class InteriorSightNew {
        @Patch.OnEnter(skipOn = true)
        public static boolean enter(@Patch.This zombie.characters.IsoZombie zombie,
                @Patch.Argument(0) zombie.iso.IsoMovingObject target) {
            return Vision.blocksSight(zombie, target);
        }
    }

    @Patch(className = "zombie.characters.IsoZombie", methodName = "spottedOld", strictMatch = true)
    public static final class InteriorSightOld {
        @Patch.OnEnter(skipOn = true)
        public static boolean enter(@Patch.This zombie.characters.IsoZombie zombie,
                @Patch.Argument(0) zombie.iso.IsoMovingObject target) {
            return Vision.blocksSight(zombie, target);
        }
    }

    @Patch(className = "zombie.characters.IsoZombie", methodName = "isTargetVisible", strictMatch = true)
    public static final class InteriorTargetSight {
        @Patch.OnExit
        public static void exit(@Patch.This zombie.characters.IsoZombie zombie,
                @Patch.Return(readOnly = false) boolean visible) {
            if (visible && Vision.blocksSight(zombie, zombie.getTarget())) visible = false;
        }
    }

    @Patch(className = "zombie.iso.weather.fx.ParticleRectangle", methodName = "render", strictMatch = true)
    public static final class CabinWeatherParticles {
        // Keep the typed receiver: ZB must resolve this class before transforming
        // WeatherParticle, whose parent field otherwise loads it during advice installation.
        @Patch.OnEnter
        public static void enter(@Patch.This zombie.iso.weather.fx.ParticleRectangle rectangle) {
            Weather.beginParticles(rectangle);
        }
        @Patch.OnExit(onThrowable = Throwable.class)
        public static void exit() { Weather.endParticles(); }
    }

    @Patch(className = "zombie.iso.weather.fx.WeatherParticle", methodName = "render", strictMatch = true)
    public static final class CabinSnow {
        @Patch.OnEnter(skipOn = true)
        public static boolean enter(@Patch.This zombie.iso.weather.fx.WeatherParticle particle,
                @Patch.Argument(0) float x, @Patch.Argument(1) float y) {
            return particle instanceof zombie.iso.weather.fx.SnowParticle
                    && Weather.skipParticle(particle, x, y);
        }
    }

    @Patch(className = "zombie.iso.weather.fx.RainParticle", methodName = "render", strictMatch = true)
    public static final class CabinRain {
        @Patch.OnEnter(skipOn = true)
        public static boolean enter(@Patch.This zombie.iso.weather.fx.RainParticle particle,
                @Patch.Argument(0) float x, @Patch.Argument(1) float y) {
            return Weather.skipParticle(particle, x, y);
        }
    }

    @Patch(className = "zombie.core.skinnedmodel.model.Model", methodName = "DrawVehicle", strictMatch = true)
    public static final class VehicleDraw {
        /** Returning true skips the draw (ME: LENS' inside on a camper you are not in). */
        @Patch.OnEnter(skipOn = true)
        public static boolean enter(@Patch.This Model model,
                                    @Patch.Argument(0) ModelSlotRenderData slot,
                                    @Patch.Argument(1) ModelInstanceRenderData inst) {
            return Cutaway.beginVehicleDraw(model, slot, inst);
        }

        @Patch.OnExit(onThrowable = Throwable.class)
        public static void exit(@Patch.Argument(0) ModelSlotRenderData slot,
                                @Patch.Argument(1) ModelInstanceRenderData inst) {
            Cutaway.endVehicleDraw(slot, inst);
        }
    }

    /** After a sub-model of a vehicle is drawn: after the last one of the camper you are in, the loose items. */
    @Patch(className = "zombie.core.skinnedmodel.model.ModelInstanceRenderData", methodName = "RenderVehicle", strictMatch = true)
    public static final class AfterVehicleModel {
        @Patch.OnExit
        public static void exit(@Patch.This ModelInstanceRenderData inst, @Patch.Argument(0) ModelSlotRenderData slot) {
            Loose.afterModel(inst, slot);
        }
    }

    /**
     * After a vehicle queued its own draw: the animals inside the one you are in (see {@link Animals}). BaseVehicle.render
     * queues the vehicle through IsoSprite.renderVehicle; the hook sits on the latter, which renderers that replace the
     * cell's object pass (the PZ Optimization mod) still call.
     */
    @Patch(className = "zombie.iso.sprite.IsoSprite", methodName = "renderVehicle", strictMatch = true)
    public static final class AfterVehicleRender {
        @Patch.OnExit
        public static void exit(@Patch.Argument(1) IsoObject object) {
            if (object instanceof BaseVehicle vehicle) {
                Animals.afterVehicleRender(vehicle);
            }
        }
    }

    /** The world camera of an animated model sets the model's depth from its own square; the animals inside take the cabin's. */
    @Patch(className = "zombie.core.skinnedmodel.advancedanimation.AnimatedModel$WorldModelCamera", methodName = "Begin", strictMatch = true)
    public static final class AnimalDepth {
        @Patch.OnExit
        public static void exit() {
            Animals.afterCameraBegin();
        }
    }

    @Patch(className = "zombie.core.skinnedmodel.model.ModelInstanceRenderData", methodName = "RenderCharacter", strictMatch = true)
    public static final class CabinDepth {
        @Patch.OnEnter
        public static void enter(@Patch.This ModelInstanceRenderData inst, @Patch.Argument(0) ModelSlotRenderData slot) {
            Cutaway.alignCabinDepth(slot, inst);
        }
    }

    @Patch(className = "zombie.core.skinnedmodel.model.Model", methodName = "CharacterModelCameraBegin", strictMatch = true)
    public static final class CabinFacing {
        @Patch.OnExit
        public static void exit(@Patch.Argument(0) ModelSlotRenderData slot) {
            Cutaway.orientCabinCharacter(slot);
        }
    }

    @Patch(className = "zombie.characters.IsoPlayer", methodName = "checkActionGroup", strictMatch = true)
    public static final class CheckActionGroup {
        @Patch.OnEnter
        public static void enter(@Patch.This IsoPlayer player) {
            Standing.beginChoosing(player);
        }

        @Patch.OnExit(onThrowable = Throwable.class)
        public static void exit() {
            Standing.endChoosing();
        }
    }

    @Patch(className = "zombie.characters.IsoPlayer", methodName = "updateWhileInVehicle", strictMatch = true)
    public static final class UpdateWhileInVehicle {
        @Patch.OnEnter
        public static void enter(@Patch.This IsoPlayer player) {
            Standing.beginChoosing(player);
        }

        @Patch.OnExit(onThrowable = Throwable.class)
        public static void exit() {
            Standing.endChoosing();
        }
    }

    @Patch(className = "zombie.characters.IsoPlayer", methodName = "GetAnimSetName", strictMatch = true)
    public static final class AnimSetName {
        @Patch.OnExit
        public static void exit(@Patch.This IsoPlayer player, @Patch.Return(readOnly = false) String name) {
            name = Standing.animSetFor(player, name);
        }
    }

    @Patch(className = "zombie.characters.action.ActionGroup", methodName = "getActionGroup", strictMatch = true)
    public static final class GetActionGroup {
        @Patch.OnExit
        public static void exit(@Patch.Argument(0) String name, @Patch.Return(readOnly = false) ActionGroup group) {
            group = Standing.groupFor(name, group);
        }
    }

    /** Scope native trait lookups to a single player update so the panic replacement
     * cannot affect trait reads elsewhere in the game. */
    @Patch(className = "zombie.characters.IsoGameCharacter", methodName = "updateInternal", strictMatch = true)
    public static final class PhobiaUpdate {
        @Patch.OnEnter
        public static void enter(@Patch.This IsoGameCharacter character) {
            Phobia.beginUpdate(character);
        }

        @Patch.OnExit(onThrowable = Throwable.class)
        public static void exit(@Patch.This IsoGameCharacter character) {
            Phobia.endUpdate(character);
        }
    }

    /** Suppress only the two direct native trait queries in updateInternal. */
    @Patch(className = "zombie.characters.traits.CharacterTraits", methodName = "get", strictMatch = true)
    public static final class PhobiaTraitLookup {
        @Patch.OnExit
        public static void exit(@Patch.This CharacterTraits traits,
                @Patch.Argument(0) CharacterTrait trait,
                @Patch.Return(readOnly = false) boolean value) {
            value = Phobia.traitResult(traits, trait, value);
        }
    }
}
