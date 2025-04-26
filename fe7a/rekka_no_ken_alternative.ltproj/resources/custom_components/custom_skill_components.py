from __future__ import annotations

from app.data.database.components import ComponentType
from app.data.database.database import DB
from app.data.database.skill_components import SkillComponent, SkillTags
from app.engine import (action, banner, combat_calcs, engine, equations,
                        image_mods, item_funcs, item_system, skill_system,
                        target_system)
from app.engine.game_state import game
from app.engine.objects.unit import UnitObject
from app.utilities import utils, static_random
from app.utilities.enums import Strike
from app.engine.combat import playback as pb


class DoNothing(SkillComponent):
    nid = 'do_nothing'
    desc = 'does nothing'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 1

class Stax(SkillComponent):
    nid = 'stax'
    desc = "Skill can be applied to a unit multiple times"
    tag = SkillTags.ATTRIBUTE

    expose = ComponentType.Int

    value = 999
	
class NineLivesMiracle(SkillComponent):
    nid = 'nine_lives_event'
    desc = "Unit cannot go beneath 1 HP. Removes a stack of the skill afterwards."
    tag = SkillTags.COMBAT2
    
    expose = ComponentType.Skill

    def after_take_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        did_something = False
        for act in reversed(actions):
            if isinstance(act, action.ChangeHP) and -act.num >= act.old_hp and act.unit == unit:
                act.num = -act.old_hp + 1
                did_something = True
                playback.append(pb.DefenseHitProc(unit, self.skill))

        if did_something:
            action.do(action.RemoveSkill(unit, self.value, 1))

class Powerstaff(SkillComponent):
	nid = 'powerstaff'
	desc = 'After using a staff, unit can move again.'
	tag = SkillTags.MOVEMENT
	
	def end_combat(self, playback, unit, item, target, item2, mode):
		playbacks = [p for p in playback if p.nid in ('mark_hit', 'heal_hit') ]
		if item_system.weapon_type(unit, item) == 'Staff' and any(p.attacker is unit for p in playbacks):
			action.do(action.Reset(unit))
			action.do(action.TriggerCharge(unit, self.skill))
	
			
class CombatArtist(SkillComponent):
    nid = 'combat_artist'
    desc = 'After using a combat art, unit can move again'
    tag = SkillTags.MOVEMENT
	
    def end_combat(self, playback, unit, item, target, item2, mode):
        playbacks = [p for p in playback if p.nid in ('attack_pre_proc')]
        if any(p.unit is unit for p in playbacks):
            action.do(action.Reset(unit))
            action.do(action.TriggerCharge(unit, self.skill))

class SecondWind(SkillComponent):
    nid = 'second_wind'
    desc = 'If the unit misses an attack, unit can move again'
    tag = SkillTags.MOVEMENT
	
    def end_combat(self, playback, unit, item, target, item2, mode):
        playbacks = [p for p in playback if p.nid in ('mark_miss')]
        if any(p.attacker is unit for p in playbacks):
            action.do(action.Reset(unit))
            action.do(action.TriggerCharge(unit, self.skill))
	
class GiveBacker(SkillComponent):
	nid = 'givebacker'
	desc = "Adds damage equal to HP lost."
	tag = SkillTags.COMBAT

	def modify_damage(self, unit, item):
		value = unit.get_max_hp() - unit.get_hp()
		return value

class EvalGaleforce(SkillComponent):
    nid = 'eval_galeforce'
    desc = "Unit can move again if conditions are met. Value must resolve to a Boolean."
    tag = SkillTags.CUSTOM

    expose = ComponentType.String
    value = ''
    author = 'Lord_Tweed'

    def end_combat(self, playback, unit, item, target, item2, mode):
        from app.engine import evaluate
        try:
            x = bool(evaluate.evaluate(self.value, unit, target, unit.position, {'item': item, 'item2': item2, 'mode': mode}))
            if x:
                action.do(action.Reset(unit))
                action.do(action.TriggerCharge(unit, self.skill))
        except Exception as e:
            print("%s: Could not evaluate EvalGaleforce condition %s" % (e, self.value))
			
class EventAfterCombat(SkillComponent):
    nid = 'event_after_combat'
    desc = 'Calls event after any combat'
    tag = SkillTags.ADVANCED

    expose = ComponentType.Event
    value = ''

    def end_combat(self, playback, unit: UnitObject, item, target: UnitObject, item2, mode):
        game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'mode': mode, 'item2': item2})
		
		
class TrueMiracleEventAfterCombat(SkillComponent):
    nid = 'true_miracle_event_after_combat'
    desc = "Unit cannot go beneath 1 HP. An event will occur after combat once this effect triggers."
    tag = SkillTags.COMBAT2
    
    expose = ComponentType.Event
    value = ''
	
    _did_something = False 

    def after_take_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        for act in reversed(actions):
            if isinstance(act, action.ChangeHP) and -act.num >= act.old_hp and act.unit == unit:
                act.num = -act.old_hp + 1
                self._did_something = True
                playback.append(pb.DefenseHitProc(unit, self.skill))
	
    def end_combat(self, playback, unit: UnitObject, item, target: UnitObject, item2, mode):
        if self._did_something and target:
            game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'mode': mode, 'item2': item2})
        self._did_something = False			
        
class EventAfterCombatWhenHit(SkillComponent):
    nid = 'event_after_combat_when_hit'
    desc = 'Calls event after any combat where unit is hit'
    tag = SkillTags.ADVANCED

    expose = ComponentType.Event
    value = ''
    
    _got_hit = False
    
    def after_take_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        if strike == Strike.HIT or strike == Strike.CRIT:
            self._got_hit = True

    def end_combat(self, playback, unit: UnitObject, item, target: UnitObject, item2, mode):
        if self._got_hit and target:
            game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'mode': mode, 'item2': item2})
        self._got_hit = False
        
class EventWhenHit(SkillComponent):
    nid = 'event_when_hit'
    desc = 'Calls event when unit is hit'
    tag = SkillTags.ADVANCED

    expose = ComponentType.Event
    value = ''
    
    def after_take_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        if strike == Strike.HIT or strike == Strike.CRIT:
            game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'mode': mode, 'item2': item2})

class EventAfterStrike(SkillComponent):
    nid = 'event_after_strike'
    desc = 'Calls event when unit makes an attack'
    tag = SkillTags.ADVANCED

    expose = ComponentType.Event
    value = ''
    
    def after_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'mode': mode, 'item2': item2})
        
class EventAfterHit(SkillComponent):
    nid = 'event_after_hit'
    desc = 'Calls event when unit makes an attack that lands'
    tag = SkillTags.ADVANCED

    expose = ComponentType.Event
    value = ''
    
    def after_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        if strike == Strike.HIT or strike == Strike.CRIT:
            game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'mode': mode, 'item2': item2})
            
class EventAfterCrit(SkillComponent):
    nid = 'event_after_crit'
    desc = 'Calls event when unit makes an attack that lands a crit'
    tag = SkillTags.ADVANCED

    expose = ComponentType.Event
    value = ''
    
    def after_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        if strike == Strike.CRIT:
            game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'mode': mode, 'item2': item2})
            
class EventOnUpkeep(SkillComponent):
    nid = 'event_on_upkeep'
    desc = "Triggers the designated event at upkeep"
    tag = SkillTags.TIME

    expose = ComponentType.Event
    value = ''
    
    def on_upkeep(self, actions, playback, unit):
        game.events.trigger_specific_event(self.value, unit, unit, unit.position, {'item': None, 'mode': None})
        
class CannotUseSpecificItem(SkillComponent):
    nid = 'cannot_use_specific_item'
    desc = "Unit cannot use or equip item with matching UID"
    tag = SkillTags.BASE
    
    expose = ComponentType.Int
    value = 1

    def available(self, unit, item) -> bool:
        return item.uid != self.value
        
class CanOnlyUseSpecificItem(SkillComponent):
    nid = 'can_only_use_specific_item'
    desc = "Unit can only use or equip item with matching NID"
    tag = SkillTags.BASE
    
    expose = ComponentType.String
    value = 1

    def available(self, unit, item) -> bool:
        return item.nid == self.value
        
class CannotUseItemsExceptArmor(SkillComponent):
    nid = 'cannot_use_items_except_armor'
    desc = "Okay"
    tag = SkillTags.BASE

    def available(self, unit, item) -> bool:
        return item_system.weapon_type(unit, item) == 'Gear'
        
class EventBeforeCombat(SkillComponent):
    nid = 'event_before_combat'
    desc = 'Calls event before any combat'
    tag = SkillTags.ADVANCED

    expose = ComponentType.Event
    value = ''

    def start_combat(self, playback, unit: UnitObject, item, target: UnitObject, item2, mode):
        game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'item2': item2, 'mode': mode})
        
class TrueMiracleEvent(SkillComponent):
    nid = 'true_miracle_event'
    desc = "Unit cannot go beneath 1 HP. An event will occur once this effect triggers."
    tag = SkillTags.COMBAT2
    
    expose = ComponentType.Event
    value = ''

    def after_take_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        did_something = False
        for act in reversed(actions):
            if isinstance(act, action.ChangeHP) and -act.num >= act.old_hp and act.unit == unit:
                act.num = -act.old_hp + 1
                did_something = True
                playback.append(pb.DefenseHitProc(unit, self.skill))

        if did_something:
            actions.append(action.TriggerCharge(unit, self.skill))
            game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'item2': item2, 'mode': mode})
            
class EventWhenDodging(SkillComponent):
    nid = 'event_when_dodging'
    desc = 'Calls event when unit dodges'
    tag = SkillTags.ADVANCED

    expose = ComponentType.Event
    value = ''
    
    def after_take_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        if strike != Strike.HIT and strike != Strike.CRIT:
            game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'mode': mode, 'item2': item2})

class Disvantage(SkillComponent):
    nid = 'disvantage'
    desc = "Why isn't this a default component?"
    tag = SkillTags.COMBAT2

    def disvantage(self, unit):
        return True
		
class EventOnStrike(SkillComponent):
    nid = 'event_on_strike'
    desc = "Activate the specified event after performing a strike (hit or miss)"
    tag = SkillTags.CUSTOM
    
    expose = ComponentType.Event
    value = ''

    def after_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': None, 'mode': None})