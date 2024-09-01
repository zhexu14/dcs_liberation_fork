local filter_threatening_units = function(unit, args)
	if unit:getCoalition() == coalition.side.NEUTRAL then
		return true  -- nothing to do if unit is neutral
	end
    if unit:getCoalition() == args.player_unit:getCoalition() then
		return true  -- nothing to do if unit is friendly
    end
	if unit:getDesc()["category"] ~= Unit.Category.AIRPLANE then
	    return true  -- nothing to do if unit is not an airplane
	end
	local unit_position = unit:getPoint()
    local player_velocity = args.player_unit:getVelocity()
    local player_position = args.player_unit:getPoint()
	local dot = player_velocity.x * ( unit_position.x - player_position.x ) + 
                player_velocity.y * ( unit_position.y - player_position.y ) + 
                player_velocity.z * ( unit_position.z - player_position.z )
	if dot > 0 then
		return true  -- unit is infront of player unit
	end
	
	args.threatening_units[#args.threatening_units + 1] = unit
	return true
end

local cover_player_unit = function(player_unit, range)
	if player_unit:getGroup():getSize() == 1 then
		return true  -- no wingmen, nothing to do
	end
	
	-- find available wingmen
	local first_available_wingman = nil
	for index, unit in pairs(player_unit:getGroup():getUnits()) do
		if unit:getName() ~= player_unit:getName() then
			if not unit:getController():hasTask() then
				first_available_wingman = unit
				break
			end
		end
	end
	
	if first_available_wingman == nil then
		return true -- no available wingmen
	end
	
	-- find threatening enemy units
	local args = {}
	args.threatening_units = {}
	args.player_unit = player_unit
	local player_position = player_unit:getPoint()
	local search_volume = {
		id = world.VolumeType.SPHERE,
		params = { point = player_position,
				   radius = range}
	}
	world.searchObjects(Object.Category.UNIT, search_volume, filter_threatening_units, args)
	for index, unit in pairs(args.threatening_units) do
		trigger.action.outText(unit:getName(),5)
		attack_unit_task = { 
		  id = 'AttackUnit', 
		  params = { 
			unitId = unit:getObjectID()
		 } 
		}
		first_available_wingman:getController():pushTask(attack_unit_task)
		break
	end
end

local run = function(args)
	for index, player_unit in pairs(coalition.getPlayers(coalition.side.BLUE)) do
		cover_player_unit(player_unit, args['range'])
	end
	for index, player_unit in pairs(coalition.getPlayers(coalition.side.RED)) do
		cover_player_unit(player_unit, args['range'])
	end
	return timer.getTime() + args['delay']
end


local args = {}
args['range'] = 1000000
args['delay'] = 30
timer.scheduleFunction(run, args, timer.getTime() + 1)