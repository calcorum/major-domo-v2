# Week 19 Transaction Recovery

## Overview

This script recovers the Week 19 transactions that were lost due to the `/dropadd` database persistence bug. These transactions were posted to Discord but never saved to the database.

## The Bug

**Root Cause**: The `/dropadd` command was missing a critical `create_transaction_batch()` call in the scheduled submission handler.

**Impact**: Week 19 transactions were:
- ✅ Created in memory
- ✅ Posted to Discord #transaction-log
- ❌ **NEVER saved to database**
- ❌ Lost when bot restarted

**Result**: The weekly freeze task found 0 transactions to process for Week 19.

## Recovery Process

### 1. Input Data

File: `.claude/week-19-transactions.md`

Contains 3 teams with 10 total moves:
- **Zephyr (DEN)**: 2 moves
- **Cavalry (CAN)**: 4 moves
- **Whale Sharks (WAI)**: 4 moves

### 2. Script Usage

```bash
# Step 1: Dry run to verify parsing and lookups
python scripts/recover_week19_transactions.py --dry-run

# Step 2: Review the preview output
# Verify all players and teams were found correctly

# Step 3: Execute to PRODUCTION (CRITICAL!)
python scripts/recover_week19_transactions.py --prod

# Or skip confirmation (use with extreme caution)
python scripts/recover_week19_transactions.py --prod --yes
```

**⚠️ IMPORTANT**: By default, the script uses whatever database is configured in `.env`. Use the `--prod` flag to explicitly send to production (`api.sba.manticorum.com`).

### 3. What the Script Does

1. **Parse** `.claude/week-19-transactions.md`
2. **Lookup** all players and teams via API services
3. **Validate** that all data is found
4. **Preview** all transactions that will be created
5. **Ask for confirmation** (unless --yes flag)
6. **POST** to database via `transaction_service.create_transaction_batch()`
7. **Report** success or failure for each team

### 4. Transaction Settings

All recovered transactions are created with:
- `week=19` - Correct historical week
- `season=12` - Current season
- `frozen=False` - Already processed (past thaw period)
- `cancelled=False` - Active transactions
- Unique `moveid` per team: `Season-012-Week-19-{timestamp}`

## Command-Line Options

- `--dry-run` - Parse and validate only, no database changes
- `--prod` - **Send to PRODUCTION database** (`api.sba.manticorum.com`) instead of dev
- `--yes` - Auto-confirm without prompting
- `--season N` - Override season (default: 12)
- `--week N` - Override week (default: 19)

**⚠️ DATABASE TARGETING:**
- **Without `--prod`**: Uses database from `.env` file (currently `sbadev.manticorum.com`)
- **With `--prod`**: Overrides to production (`api.sba.manticorum.com`)

## Example Output

### Dry Run Mode

```
======================================================================
TRANSACTION RECOVERY PREVIEW - Season 12, Week 19
======================================================================

Found 3 teams with 10 total moves:

======================================================================
Team: DEN (Zephyr)
Move ID: Season-012-Week-19-1761444914
Week: 19, Frozen: False, Cancelled: False

1. Fernando Cruz (0.22)
   From: DENMiL → To: DEN
   Player ID: 11782

2. Brandon Pfaadt (0.25)
   From: DEN → To: DENMiL
   Player ID: 11566

======================================================================
[... more teams ...]

🔍 DRY RUN MODE - No changes made to database
```

### Successful Execution

```
======================================================================
✅ RECOVERY COMPLETE
======================================================================

Team DEN: 2 moves (moveid: Season-012-Week-19-1761444914)
Team CAN: 4 moves (moveid: Season-012-Week-19-1761444915)
Team WAI: 4 moves (moveid: Season-012-Week-19-1761444916)

Total: 10 player moves recovered

These transactions are now in the database with:
  - Week: 19
  - Frozen: False (already processed)
  - Cancelled: False (active)

Teams can view their moves with /mymoves
======================================================================
```

## Verification

After running the script, verify the transactions were created:

1. **Database Check**: Query transactions table for `week=19, season=12`
2. **Discord Commands**: Teams can use `/mymoves` to see their transactions
3. **Log Files**: Check `logs/recover_week19.log` for detailed execution log

## Troubleshooting

### Player Not Found

```
⚠️  Player not found: PlayerName
```

**Solution**: Check the exact player name spelling in `.claude/week-19-transactions.md`. The script uses fuzzy matching but exact matches work best.

### Team Not Found

```
❌ Team not found: ABC
```

**Solution**: Verify the team abbreviation exists in the database for season 12. Check the `TEAM_MAPPING` dictionary in the script.

### API Error

```
❌ Error posting transactions for DEN: [error message]
```

**Solution**:
1. Check API server is running
2. Verify `API_TOKEN` is valid
3. Check network connectivity
4. Review `logs/recover_week19.log` for details

## Safety Features

- ✅ **Dry-run mode** for safe testing
- ✅ **Preview** shows exact transactions before posting
- ✅ **Confirmation prompt** (unless --yes)
- ✅ **Per-team batching** limits damage on errors
- ✅ **Comprehensive logging** to `logs/recover_week19.log`
- ✅ **Validation** of all player/team lookups before posting

## Rollback

If you need to undo the recovery:

1. Check `logs/recover_week19.log` for transaction IDs
2. Use `transaction_service.cancel_transaction(moveid)` for each
3. Or manually update database: `UPDATE transactions SET cancelled=1 WHERE moveid='Season-012-Week-19-{timestamp}'`

## The Fix

The underlying bug has been fixed in `views/transaction_embed.py`:

```python
# NEW CODE (lines 243-248):
# Mark transactions as frozen for weekly processing
for txn in transactions:
    txn.frozen = True

# POST transactions to database
created_transactions = await transaction_service.create_transaction_batch(transactions)
```

**This ensures all future `/dropadd` transactions are properly saved to the database.**

## Files

- `scripts/recover_week19_transactions.py` - Main recovery script
- `.claude/week-19-transactions.md` - Input data
- `logs/recover_week19.log` - Execution log
- `scripts/README_recovery.md` - This documentation
