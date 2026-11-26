<?php
/**
 * Plugin Name: Group Services Band
 * Description: フッターの直前に、グループサービスの紹介の帯を表示します（mu-plugins に置いて使います）。
 * Version: 1.1.0
 * Requires at least: 6.0
 * Requires PHP: 7.4
 * Author: 株式会社コンテンシャル
 * License: GPL-2.0-or-later
 * License URI: https://www.gnu.org/licenses/gpl-2.0.html
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * 帯の HTML と画像は、このファイルと同じ場所の group-services-band/ に置く
 * （mu-plugins は直下の PHP しか読み込まないため、本体はこの 1 ファイルにまとめる）。
 */
const GSBAND_DIR = __DIR__ . '/group-services-band';

/** GitHub から取ってきた帯の控え（アップロードの置き場の下）。 */
const GSBAND_CACHE_SUBDIR = 'group-services-band';

/** 帯を取りに行く定期実行のフック名。 */
const GSBAND_CRON_HOOK = 'gsband_refresh';

require_once GSBAND_DIR . '/group-services-remote.php';

/** band.html の中で、画像の置き場として書かれているパス（実際の URL に置き換える）。 */
const GSBAND_ASSET_PLACEHOLDER = '/wp-content/mu-plugins/group-services-band/assets/';

/** どの帯を取りに行くか（services.json の id。site.txt に書いてある）。 */
function gsband_site_id() {
	$file = GSBAND_DIR . '/site.txt';
	return is_readable( $file ) ? trim( (string) file_get_contents( $file ) ) : '';
}

/** 控えのファイルの絶対パス。 */
function gsband_cache_file() {
	$uploads = wp_upload_dir( null, false );
	if ( empty( $uploads['basedir'] ) ) {
		return '';
	}
	return trailingslashit( $uploads['basedir'] ) . GSBAND_CACHE_SUBDIR . '/band.html';
}

/** GitHub から帯を取ってきて、控えを新しくする（1 時間ごとの定期実行から呼ぶ）。 */
function gsband_refresh() {
	$site_id = gsband_site_id();
	$cache   = gsband_cache_file();
	if ( '' === $site_id || '' === $cache ) {
		return;
	}
	Contencial_Group_Services_Remote::refresh( $site_id, $cache );
}
add_action( GSBAND_CRON_HOOK, 'gsband_refresh' );

/** 定期実行を登録する（まだ無いときだけ）。 */
function gsband_schedule() {
	if ( ! wp_next_scheduled( GSBAND_CRON_HOOK ) ) {
		wp_schedule_event( time() + 60, 'hourly', GSBAND_CRON_HOOK );
	}
}
add_action( 'init', 'gsband_schedule' );

/**
 * 帯の HTML を返す。出さないときは空文字。
 *
 * GitHub から取ってきた控えがあればそれを、無ければ同じ場所の band.html を出す。
 * どちらも無い・読めない・中身が帯でないときは、何も出さない（ページはそのまま出る）。
 */
function gsband_html() {
	static $html = null;
	if ( null !== $html ) {
		return $html;
	}
	$html = '';

	$cache = gsband_cache_file();
	if ( '' !== $cache ) {
		$remote = Contencial_Group_Services_Remote::read( $cache );
		if ( null !== $remote ) {
			$html = $remote;
			return $html;
		}
	}

	$file = GSBAND_DIR . '/band.html';
	if ( ! is_readable( $file ) ) {
		return $html;
	}
	$raw = file_get_contents( $file );
	if ( ! is_string( $raw ) || false === strpos( $raw, '<section class="cgs"' ) ) {
		return $html;
	}

	// 画像の URL を、このプラグインの実際の置き場に合わせる。
	$base = wp_parse_url( plugins_url( 'group-services-band/assets/', __FILE__ ), PHP_URL_PATH );
	if ( is_string( $base ) && '' !== $base ) {
		$raw = str_replace( GSBAND_ASSET_PLACEHOLDER, esc_attr( $base ), $raw );
	}

	$html = $raw;
	return $html;
}

/** このリクエストで帯を出すか。 */
function gsband_should_run() {
	if ( defined( 'GSBAND_DISABLED' ) && GSBAND_DISABLED ) {
		return false;
	}
	if ( is_admin() || is_feed() || is_robots() || is_embed() || is_trackback() || is_customize_preview() ) {
		return false;
	}
	if ( wp_doing_ajax() || ( defined( 'REST_REQUEST' ) && REST_REQUEST ) || ( defined( 'XMLRPC_REQUEST' ) && XMLRPC_REQUEST ) ) {
		return false;
	}
	/**
	 * 帯を出すかどうかを変えるフィルター。false を返すと出さない。
	 *
	 * @param bool $enabled 既定は true。
	 */
	return (bool) apply_filters( 'gsband_enabled', true );
}

/**
 * ページの出力の中の、フッターの開始タグの直前に帯を差し込む。
 *
 * フッターが見つからないページ・HTML でない出力は、そのまま返す。
 *
 * @param string $buffer ページの出力。
 * @return string
 */
function gsband_inject( $buffer ) {
	if ( ! is_string( $buffer ) || '' === $buffer || false !== strpos( $buffer, '<section class="cgs"' ) ) {
		return $buffer;
	}
	$band = gsband_html();
	if ( '' === $band ) {
		return $buffer;
	}

	/**
	 * フッターの開始タグを探す正規表現を変えるフィルター。
	 *
	 * @param string $pattern 既定は class に site-footer を含む footer 要素。
	 */
	$pattern = apply_filters( 'gsband_footer_pattern', '/<footer\b[^>]*\bclass=(["\'])[^"\']*\bsite-footer\b[^"\']*\1[^>]*>/i' );
	if ( ! is_string( $pattern ) || 1 !== @preg_match_all( $pattern, $buffer, $m, PREG_OFFSET_CAPTURE ) ) {
		// 見つからない・複数ある・正規表現が不正なときは、何もしない。
		return $buffer;
	}
	$pos = $m[0][0][1];

	return substr( $buffer, 0, $pos ) . $band . substr( $buffer, $pos );
}

/** 表側のページで、出力をためて帯を差し込む。 */
function gsband_start() {
	if ( ! gsband_should_run() || '' === gsband_html() ) {
		return;
	}
	ob_start( 'gsband_inject' );
}
add_action( 'template_redirect', 'gsband_start', 0 );
