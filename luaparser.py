import re
from pathlib import Path
from typing import List, Dict, Any

# ── FULL B42 EVENTS LIST (from demiurgequantified + wiki) ──
KNOWN_EVENTS = {
    "AcceptedFactionInvite", "AcceptedSafehouseInvite", "AcceptedTrade", "AddXP", "DoSpecialTooltip",
    "EveryDays", "EveryHours", "EveryOneMinute", "EveryTenMinutes", "GrappleGrabCollisionCheck",
    "GrapplerLetGo", "LevelPerk", "LoadChunk", "LoadGridsquare", "MngInvReceiveItems", "OnAIStateChange",
    "OnAcceptInvite", "OnAddMessage", "OnAdminMessage", "OnAlertMessage", "OnAmbientSound",
    "OnCGlobalObjectSystemInit", "OnChallengeQuery", "OnCharacterCollide", "OnCharacterDeath",
    "OnChatWindowInit", "OnClickedAnimalForContext", "OnClientCommand", "OnClimateManagerInit",
    "OnClimateTick", "OnClimateTickDebug", "OnClothingUpdated", "OnConnectFailed", "OnConnected",
    "OnConnectionStateChanged", "OnContainerUpdate", "OnContextKey", "OnCoopJoinFailed",
    "OnCoopServerMessage", "OnCreateLivingCharacter", "OnCreatePlayer", "OnCreateSurvivor",
    "OnCreateUI", "OnCustomUIKey", "OnCustomUIKeyPressed", "OnCustomUIKeyReleased", "OnDeadBodySpawn",
    "OnDestroyIsoThumpable", "OnDeviceText", "OnDisconnect", "OnDistributionMerge", "OnDoTileBuilding2",
    "OnDoTileBuilding3", "OnDynamicMovableRecipe", "OnEnterVehicle", "OnEquipPrimary", "OnEquipSecondary",
    "OnExitVehicle", "OnFETick", "OnFillContainer", "OnFillInventoryObjectContextMenu",
    "OnFillWorldObjectContextMenu", "OnGameBoot", "OnGameStart", "OnGameStateEnter", "OnGameTimeLoaded",
    "OnGamepadConnect", "OnGamepadDisconnect", "OnGetDBSchema", "OnGetTableResult", "OnGridBurnt",
    "OnHitZombie", "OnInitGlobalModData", "OnInitModdedWeatherStage", "OnInitRecordedMedia",
    "OnInitSeasons", "OnInitWorld", "OnItemFound", "OnJoypadActivate", "OnJoypadActivateUI",
    "OnJoypadBeforeDeactivate", "OnJoypadBeforeReactivate", "OnJoypadDeactivate", "OnJoypadReactivate",
    "OnJoypadRenderUI", "OnKeyKeepPressed", "OnKeyPressed", "OnKeyStartPressed", "OnLoad",
    "OnLoadMapZones", "OnLoadRadioScripts", "OnLoadSoundBanks", "OnLoadedMapZones", "OnLoadedTileDefinitions",
    "OnMainMenuEnter", "OnMechanicActionDone", "OnMiniScoreboardUpdate", "OnModsModified", "OnMouseDown",
    "OnMouseMove", "OnMouseUp", "OnMouseWheel", "OnMultiTriggerNPCEvent", "OnNewFire", "OnNewGame",
    "OnObjectAboutToBeRemoved", "OnObjectAdded", "OnObjectCollide", "OnObjectLeftMouseButtonDown",
    "OnObjectLeftMouseButtonUp", "OnObjectRightMouseButtonDown", "OnObjectRightMouseButtonUp",
    "OnPlayerAttackFinished", "OnPlayerDeath", "OnPlayerGetDamage", "OnPlayerMove", "OnPlayerUpdate",
    "OnPostDistributionMerge", "OnPostFloorLayerDraw", "OnPostMapLoad", "OnPostRender", "OnPostSave",
    "OnPostUIDraw", "OnPreDistributionMerge", "OnPreFillInventoryObjectContextMenu",
    "OnPreFillWorldObjectContextMenu", "OnPreMapLoad", "OnPreUIDraw", "OnPressRackButton",
    "OnPressReloadButton", "OnPressWalkTo", "OnProcessAction", "OnProcessTransaction",
    "OnReceiveGlobalModData", "OnReceiveItemListNet", "OnReceiveUserlog", "OnRefreshInventoryWindowContainers",
    "OnRenderTick", "OnResetLua", "OnResolutionChange", "OnRightMouseDown", "OnRightMouseUp",
    "OnSGlobalObjectSystemInit", "OnSafehousesChanged", "OnSave", "OnScoreboardUpdate", "OnSeeNewRoom",
    "OnServerCommand", "OnServerFinishSaving", "OnServerStartSaving", "OnServerStarted",
    "OnServerStatisticReceived", "OnServerWorkshopItems", "OnSetDefaultTab", "OnSleepingTick",
    "OnSourceWindowFileReload", "OnSpawnRegionsLoaded", "OnSpawnVehicleEnd", "OnSpawnVehicleStart",
    "OnSteamFriendStatusChanged", "OnSteamGameJoin", "OnSteamRefreshInternetServers",
    "OnSteamRulesRefreshComplete", "OnSteamServerFailedToRespond2", "OnSteamServerResponded",
    "OnSteamServerResponded2", "OnSteamWorkshopItemCreated", "OnSteamWorkshopItemNotCreated",
    "OnSteamWorkshopItemNotUpdated", "OnSteamWorkshopItemUpdated", "OnSwitchVehicleSeat", "OnTabAdded",
    "OnTabRemoved", "OnTemplateTextInit", "OnThrowableExplode", "OnThunderEvent", "OnTick",
    "OnTickEvenPaused", "OnTileRemoved", "OnTriggerNPCEvent", "OnUpdateModdedWeatherStage",
    "OnUseVehicle", "OnVehicleDamageTexture", "OnWaterAmountChange", "OnWeaponHitCharacter",
    "OnWeaponHitThumpable", "OnWeaponHitTree", "OnWeaponHitXp", "OnWeaponSwing", "OnWeaponSwingHitPoint",
    "OnWeatherPeriodComplete", "OnWeatherPeriodStage", "OnWeatherPeriodStart", "OnWeatherPeriodStop",
    "OnWorldSound", "OnZombieCreate", "OnZombieDead", "OnZombieUpdate", "ReceiveFactionInvite",
    "ReceiveSafehouseInvite", "RenderOpaqueObjectsInWorld", "RequestTrade", "ReuseGridsquare",
    "SendCustomModData", "ServerPinged", "SetDragItem", "SwitchChatStream", "SyncFaction",
    "TradingUIAddItem", "TradingUIRemoveItem", "TradingUIUpdateState", "ViewBannedIPs",
    "ViewBannedSteamIDs", "ViewTickets", "onAddForageDefs", "onDisableSearchMode", "onEnableSearchMode",
    "onFillSearchIconContextMenu", "onItemFall", "onLoadModDataFromServer", "onToggleSearchMode",
    "onUpdateIcon", "preAddCatDefs", "preAddForageDefs", "preAddItemDefs", "preAddSkillDefs", "preAddZoneDefs"
}

FRAGILE_CALLS = [
    "getPlayer", "getSpecificPlayer", "getItemWithID", "setPrimaryHandItem",
    "ISTimedActionQueue", "AdjacentFreeTileFinder", "HaloTextHelper",
    "SandboxVars", "ZomboidGlobals", "luautils", "getCell", "getWorld",
    "getCore", "ISInventoryPage", "ISWorldObjectContextMenu",
    "ISBuildingMenu", "BuildingMenu", "ISRecipe", "Events.OnFillInventoryObjectContextMenu"
]

DEPRECATED_HOOKS = {
    "OnInitializeBuildingMenuRecipes", "OnInitializeBuildingMenuObjects",
    "OnFillWorldObjectContextMenu", "OnFillInventoryObjectContextMenu"
}

# Extra B42-fragile patterns
EXTRA_FRAGILE = [
    r'keyBinding', r'getCore\(\)\.getOption', r'ISContextMenu', r'ISInventoryContextMenu'
]

class LuaReferences:
    def __init__(self):
        self.references: List[Dict[str, Any]] = []

    def parse_mod_lua(self, mod_folder: str):
        folder = Path(mod_folder)
        lua_files = []
        for sub in ["client", "server", "shared", ""]:
            sub_path = folder / sub
            if sub_path.exists():
                lua_files.extend(sub_path.rglob("*.lua"))

        print(f"→ Found {len(lua_files)} Lua files")

        for lua_path in lua_files:
            try:
                content = lua_path.read_text(encoding="utf-8", errors="ignore")
                self._scan_file(lua_path, content)
            except Exception as e:
                print(f"Failed to read Lua file {lua_path.name}: {e}")

    def _scan_file(self, path: Path, content: str):
        rel_path = str(path.relative_to(path.parents[3])) if len(path.parents) > 3 else str(path)
        lines = content.splitlines()

        # Pre-compile regexes for speed
        event_pat = re.compile(r'Events\.([A-Za-z_][A-Za-z0-9_]*)\s*\.', re.IGNORECASE)
        fragile_pat = re.compile(r'\b(' + '|'.join(re.escape(kw) for kw in FRAGILE_CALLS) + r')\b')
        deprecated_pat = re.compile(r'\b(' + '|'.join(re.escape(h) for h in DEPRECATED_HOOKS) + r')\b')
        extra_pat = re.compile(r'|'.join(EXTRA_FRAGILE), re.IGNORECASE)

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue

            # ── Event validation ──
            for match in event_pat.finditer(stripped):
                event = match.group(1)
                if event not in KNOWN_EVENTS:
                    self.references.append({
                        "type": "lua_event_missing",
                        "source_file": rel_path,
                        "line": i,
                        "message": f"Event '{event}' removed or changed in Build 42 (B41-only)"
                    })

            # ── Fragile calls (now safe word-boundary) ──
            for match in fragile_pat.finditer(stripped):
                kw = match.group(1)
                self.references.append({
                    "type": "lua_fragile",
                    "source_file": rel_path,
                    "line": i,
                    "message": f"B42 fragile call: {kw} (may need update)"
                })

            # ── Deprecated hooks ──
            for match in deprecated_pat.finditer(stripped):
                hook = match.group(1)
                self.references.append({
                    "type": "lua_deprecated",
                    "source_file": rel_path,
                    "line": i,
                    "message": f"Deprecated hook/callback: {hook} (B42 removed)"
                })

            # ── Extra fragile patterns ──
            if extra_pat.search(stripped):
                self.references.append({
                    "type": "lua_keybinding",
                    "source_file": rel_path,
                    "line": i,
                    "message": "keyBinding / getCore.getOption / ISContextMenu — fragile in B42"
                })

if __name__ == "__main__":
    print("LuaReferences loaded — word-boundary checks now active")