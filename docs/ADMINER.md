# MissionControl database editor

Adminer runs inside your existing Codespace and edits the same synthetic PostgreSQL database used by MissionControl. It needs no local installation and no separate database subscription. It uses the Codespace's existing compute resources.

## Install and start

This add-on works with the original cloud setup, the Review Update, or the Merge Update. It adds only three files and does not change application code, data, credentials or your devcontainer. It does not install the merge feature on its own.

1. Upload `MissionControl_Adminer_Addon.zip` beside `compose.yaml` in the Codespace Explorer.
2. Run from the repository root:

```sh
python3 -m zipfile -e MissionControl_Adminer_Addon.zip /tmp/missioncontrol-adminer
python3 /tmp/missioncontrol-adminer/install.py .
```

Expect `Installed 3 files`. If any target file already has different content, the installer stops before changing anything. Share its filenames rather than overwriting an existing Compose override.

3. With MissionControl's database running, run:

```sh
bash scripts/adminer-start.sh
```

The first start pulls the Adminer Docker image. No application build, schema migration, database reset or Codespaces rebuild is required. If the database is stopped, start MissionControl first with `bash scripts/cloud-start.sh`.

4. In the Codespaces **Ports** panel, add port **8081** if it is absent. Confirm **Port Visibility: Private**, leave the forwarded-port protocol at **HTTP**, then select **Open in Browser**. GitHub supplies the HTTPS browser address. Port 8080 remains MissionControl; 8081 is Adminer. Do not expose PostgreSQL port 5432.

## Sign in

| Field | Value |
|---|---|
| System | PostgreSQL |
| Server | `db` |
| Username | `mc_admin` |
| Password | The value after `POSTGRES_PASSWORD=` in the existing workspace `.env` |
| Database | `missioncontrol` |

This is the database password, not APP_TOKEN, REVIEW_TOKEN, your GitHub password, or the model API key. Do not paste it into chat. If it fails, do not change `.env` to invent a new password: changing that file does not rotate credentials in an existing PostgreSQL volume.

For read-only browsing, use `mc_reader` and `READER_PASSWORD` instead. Use `mc_admin` when intentionally editing synthetic records.

## Browse and edit a record

1. Choose a table, such as **employment**, and select its data. If you land on its structure page, choose **Select data**.
2. Filter by record ID, client ID or date. For a Q3 wage test, use jobs with a start date between July 1 and September 30, 2026.
3. Record the original value, then click **Edit** for one row, change the field and select **Save**. Avoid changing IDs or client relationships manually.
4. Return to MissionControl and click **Refresh data**. Ask a new question if you want a new answer based on the changed data; previous answers remain historical.
5. Restore the original value after the test if desired. No app or container rebuild is needed for data edits.

| Table/field | Useful test |
|---|---|
| `employment.hourly_wage` | Set a valid in-period wage to 35 to change the average; set it to 1500 to create an outlier excluded from the valid-wage average |
| `enrollments.status`, `end_date` | Set status to `exited` and end_date to SQL NULL to create a missing-exit flag; use the editor's NULL control rather than typing the word NULL |
| `services.units` | A negative value creates a quality flag; only positive units count as service evidence |
| `housing.destination` | Change a valid in-period exit from `unstable` to `stable` to increase the stable-exit numerator |

These edits bypass MissionControl's approvals and its application audit log. Use the editor to set up synthetic test cases, and use MissionControl to test corrections and merges. Do not directly edit `proposed_actions`, `audit_records` or `client_merges`. Keep other reviewers off the records being edited; Adminer does not take the application-wide proposal lock, and pending proposals may need to be refreshed/replaced after direct edits.

Before extensive testing, take a database backup in the Codespaces terminal:

```sh
mkdir -p .backups
docker compose exec -T db pg_dump -U mc_admin -d missioncontrol -Fc > ".backups/demo-before-editing-$(date +%Y%m%d-%H%M%S).dump"
```

Backups here remain in this Codespace and are ignored by Git. Do not delete the Codespace before exporting a backup you want to keep.

## Stop, resume and save

Log out of Adminer when done, then stop its container:

```sh
docker compose --profile database-tools stop adminer
```

Start it again with `bash scripts/adminer-start.sh`. Its service is behind the optional `database-tools` Compose profile, so normal app startup does not create/start it automatically. The image has no automatic restart policy. Stopping Adminer leaves the database and MissionControl running.

Commit the add-on:

```sh
git add compose.override.yaml scripts/adminer-start.sh docs/ADMINER.md
git commit -m "Add optional private Adminer database editor"
git push
```

The test script's explicit Compose files exclude this development add-on. Keep this optional editor out of future production/Vultr deployment configuration.

## Live AI and pgAdmin

A live model does not require Adminer or pgAdmin. MissionControl's backend already connects to PostgreSQL and exposes controlled read/proposal tools to the model. Adminer is for human browsing and testing. pgAdmin is an alternative administration interface if you later want more advanced database tools; it does not improve the model or enable its database connection.

## Validation and reference

The add-on uses the Docker Official Image `adminer:6.1.1`, which includes the PostgreSQL driver. The official image documents its HTTP port 8080 and `ADMINER_DEFAULT_SERVER` setting: https://hub.docker.com/_/adminer

YAML parsing and shell syntax were checked. Docker execution is unavailable in the build environment; the image pull, private-port access and database sign-in must be verified in Codespaces. No live database records were edited while preparing this add-on.
