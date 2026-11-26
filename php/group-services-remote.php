<?php
/**
 * グループサービスの帯を、GitHub の最新の中身から取ってきて、サイトの手元に控える部品。
 *
 * - refresh() は、1 時間に 1 回ほど、定期実行から呼ぶ（ページを出す処理からは呼ばない）。
 *   1. GitHub の API で、main の最新のコミットの番号を聞く
 *   2. その番号の dist/remote/<id>.html を jsDelivr から取る（コミットの番号の URL は中身が変わらない）
 *   3. 中身を確かめて、画像の URL の __CGS_REF__ をその番号に置き換え、控えのファイルに書く
 *   取れなかったとき・中身がおかしいときは、控えをそのまま残す（前の帯が出続ける）。
 * - read() は、ページを出すときに控えを読む。控えが無い・おかしいときは null（サイトの手元の帯を出す）。
 *
 * PHP 7.4 以上。フレームワークに頼らない（Laravel のサイトと WordPress のサイトで同じものを使う）。
 */

if ( ! class_exists( 'Contencial_Group_Services_Remote' ) ) {

	final class Contencial_Group_Services_Remote {

		const REPO       = 'contencial/group-services';
		const BRANCH     = 'main';
		const REF_MARK   = '__CGS_REF__';
		const BAND_MARK  = '<section class="cgs"';
		const MAX_BYTES  = 200000;
		const TIMEOUT    = 10;
		const USER_AGENT = 'contencial-group-services';

		/**
		 * 帯を取りに行って、控えを新しくする。
		 *
		 * @param string $site_id    どの帯か（services.json の id）。
		 * @param string $cache_file 控えのファイルの絶対パス。
		 * @return string 'updated'（新しくした）・'same'（変わっていない）・'error: 〜'（控えはそのまま）
		 */
		public static function refresh( $site_id, $cache_file ) {
			if ( ! is_string( $site_id ) || 1 !== preg_match( '/^[a-z0-9-]+$/', $site_id ) ) {
				return 'error: site_id';
			}
			$sha = self::get( 'https://api.github.com/repos/' . self::REPO . '/commits/heads/' . self::BRANCH, 'application/vnd.github.sha' );
			if ( null === $sha ) {
				return 'error: sha';
			}
			$sha = trim( $sha );
			if ( 1 !== preg_match( '/^[0-9a-f]{40}$/', $sha ) ) {
				return 'error: sha format';
			}
			$sha_file = $cache_file . '.sha';
			if ( is_readable( $sha_file ) && trim( (string) file_get_contents( $sha_file ) ) === $sha && null !== self::read( $cache_file ) ) {
				return 'same';
			}

			$band = self::get( 'https://cdn.jsdelivr.net/gh/' . self::REPO . '@' . $sha . '/dist/remote/' . $site_id . '.html', 'text/plain' );
			if ( null === $band ) {
				return 'error: band';
			}
			if ( ! self::looks_like_band( $band ) ) {
				return 'error: band content';
			}
			$band = str_replace( self::REF_MARK, $sha, $band );

			$dir = dirname( $cache_file );
			if ( ! is_dir( $dir ) && ! @mkdir( $dir, 0775, true ) && ! is_dir( $dir ) ) {
				return 'error: mkdir';
			}
			// 書きかけのファイルをページが読まないように、別の名前に書いてから置き換える
			$tmp = $cache_file . '.tmp' . getmypid();
			if ( false === @file_put_contents( $tmp, $band, LOCK_EX ) || ! @rename( $tmp, $cache_file ) ) {
				@unlink( $tmp );
				return 'error: write';
			}
			@file_put_contents( $sha_file, $sha . "\n", LOCK_EX );

			return 'updated';
		}

		/**
		 * 控えの帯を読む。
		 *
		 * @param string $cache_file 控えのファイルの絶対パス。
		 * @return string|null 帯の HTML。控えが無い・中身が帯でないときは null。
		 */
		public static function read( $cache_file ) {
			if ( ! is_string( $cache_file ) || ! is_file( $cache_file ) || ! is_readable( $cache_file ) ) {
				return null;
			}
			$html = @file_get_contents( $cache_file );
			if ( ! is_string( $html ) || ! self::looks_like_band( $html ) ) {
				return null;
			}

			return $html;
		}

		/**
		 * 帯として出してよい中身か（大きさ・帯の印・スクリプトが無いこと）。
		 *
		 * @param string $html 中身。
		 * @return bool
		 */
		private static function looks_like_band( $html ) {
			if ( '' === $html || strlen( $html ) > self::MAX_BYTES || false === strpos( $html, self::BAND_MARK ) ) {
				return false;
			}
			// 帯は HTML とスタイルだけ。スクリプト・イベントの属性・javascript: は受け付けない
			if ( 1 === preg_match( '/<\s*(script|iframe|object|embed|form)\b|\son[a-z]+\s*=|javascript\s*:/i', $html ) ) {
				return false;
			}

			return true;
		}

		/**
		 * GET して本文を返す。200 以外・失敗は null。
		 *
		 * @param string $url    取りに行く URL。
		 * @param string $accept Accept の値。
		 * @return string|null
		 */
		private static function get( $url, $accept ) {
			$headers = array( 'Accept: ' . $accept, 'User-Agent: ' . self::USER_AGENT );
			if ( function_exists( 'curl_init' ) ) {
				$ch = curl_init( $url );
				curl_setopt_array(
					$ch,
					array(
						CURLOPT_RETURNTRANSFER => true,
						CURLOPT_FOLLOWLOCATION => false,
						CURLOPT_CONNECTTIMEOUT => 5,
						CURLOPT_TIMEOUT        => self::TIMEOUT,
						CURLOPT_HTTPHEADER     => $headers,
						CURLOPT_PROTOCOLS      => CURLPROTO_HTTPS,
					)
				);
				$body = curl_exec( $ch );
				$code = (int) curl_getinfo( $ch, CURLINFO_RESPONSE_CODE );
				curl_close( $ch );

				return ( 200 === $code && is_string( $body ) && strlen( $body ) <= self::MAX_BYTES ) ? $body : null;
			}
			$context = stream_context_create(
				array(
					'http' => array(
						'method'          => 'GET',
						'header'          => implode( "\r\n", $headers ),
						'timeout'         => self::TIMEOUT,
						'follow_location' => 0,
						'ignore_errors'   => true,
					),
				)
			);
			$body = @file_get_contents( $url, false, $context, 0, self::MAX_BYTES + 1 );
			$status = isset( $http_response_header[0] ) ? $http_response_header[0] : '';

			return ( is_string( $body ) && strlen( $body ) <= self::MAX_BYTES && 1 === preg_match( '#^HTTP/\S+\s+200\b#', $status ) ) ? $body : null;
		}
	}
}
