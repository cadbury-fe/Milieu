from __future__ import annotations

from app.data.database.components import ComponentType
from app.data.database.database import DB
from app.data.database.item_components import ItemComponent, ItemTags
from app.engine import (action, banner, combat_calcs, engine, equations,
                        image_mods, item_funcs, item_system, skill_system,
                        target_system)
from app.engine.game_state import game
from app.engine.objects.unit import UnitObject
from app.utilities import utils, static_random


class DoNothing(ItemComponent):
    nid = 'do_nothing'
    desc = 'does nothing'
    tag = ItemTags.CUSTOM

    expose = ComponentType.Int
    value = 1

class Advance(ItemComponent):
    nid = 'advance'
    desc = "Item moves both user and target forward on hit."
    tag = ItemTags.SPECIAL
    author = "Lord Tweed"

    expose = ComponentType.Int
    value = 1

    def _check_advance(self, target, user, magnitude):
        offset_x = utils.clamp(target.position[0] - user.position[0], -1, 1)
        offset_y = utils.clamp(target.position[1] - user.position[1], -1, 1)
        new_position_user = (user.position[0] + offset_x * magnitude,
                             user.position[1] + offset_y * magnitude)
        new_position_target = (target.position[0] + offset_x * magnitude,
                               target.position[1] + offset_y * magnitude)

        mcost_user = movement_funcs.get_mcost(user, new_position_user)
        mcost_target = movement_funcs.get_mcost(target, new_position_target)

        if game.board.check_bounds(new_position_target) and \
                not game.board.get_unit(new_position_target) and \
                mcost_user <= equations.parser.movement(user) and mcost_target <= equations.parser.movement(target):
            return new_position_user, new_position_target
        return None, None

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        if not skill_system.ignore_forced_movement(target):
            new_position_user, new_position_target = self._check_advance(target, unit, self.value)
            if new_position_user and new_position_target:
                actions.append(action.ForcedMovement(unit, new_position_user))
                playback.append(pb.ShoveHit(unit, item, unit))
                actions.append(action.ForcedMovement(target, new_position_target))
                playback.append(pb.ShoveHit(unit, item, target))

class AdvanceTargetRestrict(Advance, ItemComponent):
    nid = 'advance_target_restrict'
    desc = "Suppresses the Advance command when it would be invalid."
    tag = ItemTags.SPECIAL
    author = "Lord Tweed"

    expose = ComponentType.Int
    value = 1

    def target_restrict(self, unit, item, def_pos, splash) -> bool:
        defender = game.board.get_unit(def_pos)
        positions = [result for result in self._check_advance(defender, unit, self.value)]
        if defender and all(positions) and \
                not skill_system.ignore_forced_movement(defender):
            return True
        for s_pos in splash:
            s = game.board.get_unit(s_pos)
            splash_positions = [result for result in self._check_advance(s, unit, self.value)]
            if all(splash_positions) and not skill_system.ignore_forced_movement(s):
                return True
        return False

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        pass

    def end_combat(self, playback, unit, item, target, item2, mode):
        pass


class GoldCost(ItemComponent):
    nid = 'gold_cost'
    desc = "Item subtracts the specified amount of gold upon use. If unit does not have enough gold the item will not be usable."
    tag = ItemTags.USES

    expose = ComponentType.Int
    value = 1

    def available(self, unit, item) -> bool:
        return game.get_money() >= self.value

    def start_combat(self, playback, unit, item, target, item2, mode):
        action.do(action.GainMoney(game.current_party, -self.value))

    def reverse_use(self, unit, item):
        action.do(action.GainMoney(game.current_party, self.value))

class Cleave2RangeAOE(ItemComponent):
    nid = 'cleave_2_range_aoe'
    desc = "All units within two tiles (or diagonal from the target) are affected by this attack's AOE. Leaves units with 1HP"
    tag = ItemTags.AOE

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        EnHP = game.get_unit('Ennis').current_hp
        SuHP = game.get_unit('SuzerainC21').current_hp
        true_damage = damage = target.get_hp() - 1
        if game.get_unit('SuzerainC21'):
            actions.append(action.ChangeHP(target, -damage))
            actions.append(action.SetHP(game.get_unit('SuzerainC21'), SuHP))
        elif game.get_unit('Ennis').party != 'Ennis':
            actions.append(action.ChangeHP(target, -damage))
            actions.append(action.SetHP(game.get_unit('Ennis'), EnHP))
        else:
            actions.append(action.ChangeHP(target, -damage))

        # For animation
        playback.append(pb.DamageHit(unit, item, target, damage, true_damage))
        if true_damage == 0:
            playback.append(pb.HitSound('No Damage'))
            playback.append(pb.HitAnim('MapNoDamage', target))

    def splash(self, unit, item, position) -> tuple:
        from app.engine import skill_system
        pos = position
        all_positions = {(pos[0] - 1, pos[1] - 1),
                         (pos[0], pos[1] - 1),
                         (pos[0] + 1, pos[1] - 1),
                         (pos[0] - 1, pos[1]),
                         (pos[0] + 1, pos[1]),
                         (pos[0] - 1, pos[1] + 1),
                         (pos[0], pos[1] + 1),
                         (pos[0] + 1, pos[1] + 1),
                         #
                         (pos[0] - 1, pos[1] - 2),
                         (pos[0] + 1, pos[1] - 2),
                         (pos[0] - 2, pos[1] - 1),
                         (pos[0] + 2, pos[1] - 1),
                         (pos[0] - 2, pos[1] + 1),
                         (pos[0] + 2, pos[1] + 1),
                         (pos[0] - 1, pos[1] + 2),
                         (pos[0] + 1, pos[1] + 2),
                         #
                         (pos[0] - 2, pos[1] - 2),
                         (pos[0], pos[1] - 2),
                         (pos[0] + 2, pos[1] - 2),
                         (pos[0] - 2, pos[1]),
                         (pos[0] + 2, pos[1]),
                         (pos[0] - 2, pos[1] + 2),
                         (pos[0], pos[1] + 2),
                         (pos[0] + 2, pos[1] + 2)}

        all_positions = {pos for pos in all_positions if game.tilemap.check_bounds(pos)}
        all_positions.discard(position)
        splash = all_positions
        splash = [game.board.get_unit(pos) for pos in splash]
        splash = [s.position for s in splash if s]# and skill_system.check_enemy(unit, s)]
        main_target = position if game.board.get_unit(position) else None
        return main_target, splash

    def splash_positions(self, unit, item, position) -> set:
        from app.engine import skill_system
        pos = position
        all_positions = {(pos[0] - 1, pos[1] - 1),
                         (pos[0], pos[1] - 1),
                         (pos[0] + 1, pos[1] - 1),
                         (pos[0] - 1, pos[1]),
                         (pos[0] + 1, pos[1]),
                         (pos[0] - 1, pos[1] + 1),
                         (pos[0], pos[1] + 1),
                         (pos[0] + 1, pos[1] + 1),
                         #
                         (pos[0] - 1, pos[1] - 2),
                         (pos[0] + 1, pos[1] - 2),
                         (pos[0] - 2, pos[1] - 1),
                         (pos[0] + 2, pos[1] - 1),
                         (pos[0] - 2, pos[1] + 1),
                         (pos[0] + 2, pos[1] + 1),
                         (pos[0] - 1, pos[1] + 2),
                         (pos[0] + 1, pos[1] + 2),
                         #
                         (pos[0] - 2, pos[1] - 2),
                         (pos[0], pos[1] - 2),
                         (pos[0] + 2, pos[1] - 2),
                         (pos[0] - 2, pos[1]),
                         (pos[0] + 2, pos[1]),
                         (pos[0] - 2, pos[1] + 2),
                         (pos[0], pos[1] + 2),
                         (pos[0] + 2, pos[1] + 2)}

        all_positions = {pos for pos in all_positions if game.tilemap.check_bounds(pos)}
        all_positions.discard(position)
        splash = all_positions
        # Doesn't highlight allies positions
        splash = {pos for pos in splash if not game.board.get_unit(pos)}# or skill_system.check_enemy(unit, game.board.get_unit(pos))}
        return splash

class Phasewalk(ItemComponent):
    nid = 'phasewalk'
    desc = "Item teleports user in a straight line, passing over obstacles. Provide a list of warpable terrain types"
    tag = ItemTags.SPECIAL

    expose = (ComponentType.List, ComponentType.Terrain)

    def _specially_traversable(self, unit, pos) -> int:
        """
        returns 0 if a square is ordinarily traversable
        returns 1 if a square is warpable
        returns 2 if it's not traversable and we shouldn't be able to warp over it
        """
        if movement_funcs.check_traversable(unit, pos):
            return 0
        elif game.tilemap.get_terrain(pos) in self.value:
            return 1
        else:
            return 2

    def _determine_valid_endpoints(self, unit):
        """returns dict of {target: endpoint} that can be warped to"""
        valid_endpoints = {}
        # down, up, left, right
        directions = [(0, 1), (0, -1), (-1, 0), (1, 0)]
        # should be impossible?
        if not unit.position:
            return valid_endpoints
        for delta in directions:
            current_pos = unit.position
            targetable_adj_pos = utils.tuple_add(current_pos, delta)[:]
            if not game.board.check_bounds(targetable_adj_pos): continue # if the neighbor pos doesn't even exist, skip
            if self._specially_traversable(unit, targetable_adj_pos) != 1: continue # if the neighboring pos isn't a warpable wall, skip
            while True: # if and only if there's eventually a space we can stop, and we only warp over valid walls in the meantime, this target is ok
                current_pos = utils.tuple_add(current_pos, delta)
                if not game.board.check_bounds(current_pos): break # gone off the map, skip
                status_of_current_square = self._specially_traversable(unit, current_pos)
                if status_of_current_square == 2: break # crossing over an unwarpable tile, skip
                elif status_of_current_square == 0: # made it to a standing tile, we're good
                    valid_endpoints[targetable_adj_pos] = current_pos
                    break
        return valid_endpoints

    def valid_targets(self, unit, item) -> set:
        return {pos for pos, _ in self._determine_valid_endpoints(unit).items()}

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        possible_endpoints = self._determine_valid_endpoints(unit)
        endpoint = possible_endpoints.get(target_pos, None)
        if endpoint:
            actions.append(action.Swoosh(target, endpoint))

class Charge(ItemComponent):
    nid = 'charge'
    desc = "Item moves user in a straight line at half unit movement but can't land on obstacles. Provide a list of walkable terrain types"
    tag = ItemTags.CUSTOM

    expose = (ComponentType.List, ComponentType.Terrain)

    def _specially_traversable(self, unit, pos) -> int:
        """
        returns 0 if a square is ordinarily traversable
        returns 1 if a square is warpable
        returns 2 if it's not traversable and we shouldn't be able to warp over it
        """
        if movement_funcs.check_traversable(unit, pos):
            return 0
        elif game.tilemap.get_terrain(pos) in self.value:
            return 1
        else:
            return 2

    def _determine_valid_endpoints(self, unit):
        """returns dict of {target: endpoint} that can be warped to"""
        valid_endpoints = {}
        # down, up, left, right
        directions = [(0, 1), (0, -1), (-1, 0), (1, 0)]
        movement = equations.parser.movement(unit)
        # should be impossible?
        if not unit.position:
            return valid_endpoints
        for delta in directions:
            current_pos = unit.position
            targetable_adj_pos = utils.tuple_add(current_pos, delta)[:]
            if not game.board.check_bounds(targetable_adj_pos): continue # if the neighbor pos doesn't even exist, skip
            if self._specially_traversable(unit, targetable_adj_pos) != 0: continue # if the neighboring pos isn't a warpable wall
            while True: # if and only if there's eventually a space we can stop, and we only warp over valid walls in the meantime, this target is ok
                if delta == (0, 1):
                    current_pos = utils.tuple_add((current_pos[0], current_pos[1] + (int(movement/2) - 1)), delta)
                elif delta == (0, -1):
                    current_pos = utils.tuple_add((current_pos[0], current_pos[1] - (int(movement/2) - 1)), delta)
                elif delta == (-1, 0):
                    current_pos = utils.tuple_add((current_pos[0] - (int(movement/2) - 1), current_pos[1]), delta)
                elif delta == (1, 0):
                    current_pos = utils.tuple_add((current_pos[0] + (int(movement/2) - 1), current_pos[1]), delta)
                if not game.board.check_bounds(current_pos): break # gone off the map, skip
                status_of_current_square = self._specially_traversable(unit, current_pos)
                if status_of_current_square == 2: break # crossing over an unwarpable tile, skip
                elif status_of_current_square == 0: # made it to a standing tile, we're good
                    valid_endpoints[targetable_adj_pos] = current_pos
                break
        return valid_endpoints

    def valid_targets(self, unit, item) -> set:
        return {pos for pos, _ in self._determine_valid_endpoints(unit).items()}

    #check for target restrict invalid endpoint
    def target_restrict(self, unit, item, pos, splash) -> bool:
        possible_endpoints = self._determine_valid_endpoints(unit)
        endpoint = possible_endpoints.get(pos, None)
        if unit and endpoint:
            if movement_funcs.check_traversable(unit, endpoint):
                return True
        return False

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        possible_endpoints = self._determine_valid_endpoints(unit)
        endpoint = possible_endpoints.get(target_pos, None)
        current_occupant = game.board.get_unit(endpoint)
        if endpoint:
            actions.append(action.Swoosh(target, endpoint))
            if bool(current_occupant) == True:
                new_pos = game.target_system.get_nearest_open_tile(current_occupant, endpoint)
                action.do(action.ForcedMovement(current_occupant, new_pos))

class Bullrush(ItemComponent):
    nid = 'bullrush'
    desc = "Item moves user in a straight line but can't land on obstacles. Provide a list of walkable terrain types"
    tag = ItemTags.CUSTOM

    expose = (ComponentType.List, ComponentType.Terrain)

    def _specially_traversable(self, unit, pos) -> int:
        """
        returns 0 if a square is ordinarily traversable
        returns 1 if a square is warpable
        returns 2 if it's not traversable and we shouldn't be able to warp over it
        """
        if movement_funcs.check_traversable(unit, pos):
            return 0
        elif game.tilemap.get_terrain(pos) in self.value:
            return 1
        else:
            return 2

    def _determine_valid_endpoints(self, unit):
        """returns dict of {target: endpoint} that can be warped to"""
        valid_endpoints = {}
        # down, up, left, right
        directions = [(0, 1), (0, -1), (-1, 0), (1, 0)]
        movement = equations.parser.movement(unit)
        # should be impossible?
        if not unit.position:
            return valid_endpoints
        for delta in directions:
            current_pos = unit.position
            targetable_adj_pos = utils.tuple_add(current_pos, delta)[:]
            if not game.board.check_bounds(targetable_adj_pos): continue # if the neighbor pos doesn't even exist, skip
            if self._specially_traversable(unit, targetable_adj_pos) != 0: continue # if the neighboring pos isn't a warpable wall, skip
            while True: # if and only if there's eventually a space we can stop, and we only warp over valid walls in the meantime, this target is ok
                if delta == (0, 1):
                    current_pos = utils.tuple_add((current_pos[0], current_pos[1] + (movement - 1)), delta)
                elif delta == (0, -1):
                    current_pos = utils.tuple_add((current_pos[0], current_pos[1] - (movement - 1)), delta)
                elif delta == (-1, 0):
                    current_pos = utils.tuple_add((current_pos[0] - (movement - 1), current_pos[1]), delta)
                elif delta == (1, 0):
                    current_pos = utils.tuple_add((current_pos[0] + (movement - 1), current_pos[1]), delta)
                if not game.board.check_bounds(current_pos): break # gone off the map, skip
                status_of_current_square = self._specially_traversable(unit, current_pos)
                if status_of_current_square == 2: break # crossing over an unwarpable tile, skip
                elif status_of_current_square == 0: # made it to a standing tile, we're good
                    valid_endpoints[targetable_adj_pos] = current_pos
                break
        return valid_endpoints

    def valid_targets(self, unit, item) -> set:
        return {pos for pos, _ in self._determine_valid_endpoints(unit).items()}

    #check for target restrict invalid endpoint
    def target_restrict(self, unit, item, pos, splash) -> bool:
        possible_endpoints = self._determine_valid_endpoints(unit)
        endpoint = possible_endpoints.get(pos, None)
        if unit and endpoint:
            if movement_funcs.check_traversable(unit, endpoint):
                return True
        return False

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        possible_endpoints = self._determine_valid_endpoints(unit)
        endpoint = possible_endpoints.get(target_pos, None)
        current_occupant = game.board.get_unit(endpoint)
        if endpoint:
            actions.append(action.Swoosh(target, endpoint))
            if bool(current_occupant) == True:
                new_pos = game.target_system.get_nearest_open_tile(current_occupant, endpoint)
                action.do(action.ForcedMovement(current_occupant, new_pos))

class Trace(ItemComponent):
    nid = 'trace'
    desc = "Copy an item, and add that copy to unit's inventory. Item will have only 1 use."
    tag = ItemTags.CUSTOM

    _did_trace = False

    def init(self, item):
        item.data['target_item'] = None

    def target_restrict(self, unit, item, def_pos, splash) -> bool:
        # Unit has item that can be copied
        defender = game.board.get_unit(def_pos)
        for def_item in defender.items:
            if self.item_restrict(unit, item, defender, def_item):
                return True
        return False

    def ai_targets(self, unit, item):
        positions = set()
        for other in game.units:
            if other.position and skill_system.check_enemy(unit, other):
                for def_item in other.items:
                    if self.item_restrict(unit, item, other, def_item):
                        positions.add(other.position)
                        break
        return positions

    def targets_items(self, unit, item) -> bool:
        return True

    def item_restrict(self, unit, item, defender, def_item) -> bool:
        if 'NoTrace' in def_item.tags:
            return False
        if 'Fragarach' not in def_item.nid and not def_item.data.get('uses', None):
            return False
        if item_system.is_accessory(defender, def_item):
            return False
        if not item_system.tradeable(defender, def_item) or not item_system.storeable(defender, def_item) or not item_system.discardable(defender, def_item):
            return False
        if item_funcs.inventory_full(unit, def_item):
            return False
        return True

    def on_hit(self, actions, playback, unit, item, target, item2, target_pos, mode, attack_info):
        target_item = item.data.get('target_item')
        if target_item:
            if 'Fragarach' in target_item.name:
                new_item = item_funcs.create_item(None, 'Deviant_Fragarach')
                game.register_item(new_item)
            else:
                new_item = item_funcs.create_item(None, target_item.nid)
                game.register_item(new_item)
                actions.append(action.SetObjData(new_item, 'uses', 1))
            actions.append(action.GiveItem(unit, new_item))
            self._did_trace = True

    def end_combat(self, playback, unit, item, target, item2, mode):
        if self._did_trace:
            target_item = item.data.get('target_item')
            if 'Fragarach' in target_item.name:
                new_item = item_funcs.create_item(None, 'Deviant_Fragarach')
            else:
                new_item = item_funcs.create_item(None, target_item.nid)
            game.alerts.append(banner.AcquiredItem(unit, new_item))
            game.state.change('alert')
        self._did_trace = False

    def ai_priority(self, unit, item, target, move):
        if target:
            steal_term = 0.075
            enemy_positions = utils.average_pos({other.position for other in game.units if other.position and skill_system.check_enemy(unit, other)})
            distance_term = utils.calculate_distance(move, enemy_positions)
            return steal_term + 0.01 * distance_term
        return 0