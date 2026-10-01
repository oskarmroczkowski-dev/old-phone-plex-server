-- EXAMPLE: move an existing Plex library from Windows to the phone without rescanning everything.
-- Rewrites Windows media paths (e.g. D:\Media\Movies\Film.mp4) in the Plex database to the
-- path Plex sees inside Ubuntu on the phone (/media/usb1/Media/Movies/Film.mp4).
--
-- ADAPT BEFORE USE: replace 'D:\Media\' with your old Windows folder(s) and '/media/usb1/Media/'
-- with your folder on the USB drive; check library_section_id values in your own database.
--
-- How to run (ONCE, with Plex stopped):
--   1. Back up the database first:
--        cp com.plexapp.plugins.library.db lib.db.before-migration
--   2. Run with Plex's own SQLite build (it supports Plex's custom tokenizers):
--        "/usr/lib/plexmediaserver/Plex SQLite" com.plexapp.plugins.library.db < migrate-plex-paths.sql
--   3. Start Plex, scan the libraries and empty the trash.
-- The database lives in:
--   /var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Plug-in Support/Databases/

BEGIN;
-- media file paths: Windows prefix -> phone prefix, backslashes -> slashes
UPDATE media_parts SET file = '/media/usb1/Media/' || replace(substr(file, length('D:\Media\')+1), '\', '/') WHERE file LIKE 'D:\Media\%';
-- folder paths
UPDATE directories SET path = replace(path, '\', '/');
-- external streams (e.g. subtitle files)
UPDATE media_streams SET url = replace(replace(url, 'file://D:\Media\', 'file:///media/usb1/Media/'), '\', '/') WHERE url LIKE 'file://%';
-- library root folders (one row per library; adjust ids and folder names)
DELETE FROM section_locations WHERE root_path NOT LIKE 'D:%';
UPDATE section_locations SET root_path = '/media/usb1/Media/Movies' WHERE library_section_id = 1;
UPDATE section_locations SET root_path = '/media/usb1/Media/TV Shows' WHERE library_section_id = 2;
COMMIT;

-- checks: new roots, number of migrated files, files still pointing to Windows paths (should be 0)
SELECT library_section_id, root_path FROM section_locations;
SELECT count(*) FROM media_parts WHERE file LIKE '/media/usb1/%';
SELECT count(*) FROM media_parts WHERE file LIKE '%\%' OR file LIKE '_:%';
PRAGMA integrity_check;
