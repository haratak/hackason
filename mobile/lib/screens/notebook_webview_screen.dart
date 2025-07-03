import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';
import 'package:webview_flutter/webview_flutter.dart';

class NotebookWebViewScreen extends StatefulWidget {
  final String notebookUrl;
  final String title;
  final String? childId;
  final String? notebookId;

  const NotebookWebViewScreen({
    required this.notebookUrl,
    required this.title,
    this.childId,
    this.notebookId,
    super.key,
  });

  @override
  State<NotebookWebViewScreen> createState() => _NotebookWebViewScreenState();
}

class _NotebookWebViewScreenState extends State<NotebookWebViewScreen> {
  late final WebViewController _controller;
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _initializeWebView();
  }

  void _initializeWebView() {
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(Colors.white)
      ..enableZoom(true)
      ..setUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148')
      ..setNavigationDelegate(
        NavigationDelegate(
          onProgress: (progress) {
            if (progress == 100) {
              setState(() {
                _isLoading = false;
              });
            }
          },
          onPageStarted: (url) {
            setState(() {
              _isLoading = true;
              _errorMessage = null;
            });
          },
          onPageFinished: (url) async {
            setState(() {
              _isLoading = false;
            });
            // ページが完全に読み込まれてから少し待つ
            await Future<void>.delayed(const Duration(milliseconds: 500));
            // ビデオサムネイル生成のJavaScriptコードを実行
            await _injectVideoThumbnailScript();
          },
          onWebResourceError: (error) {
            setState(() {
              _isLoading = false;
              _errorMessage = 'ページの読み込みに失敗しました: ${error.description}';
            });
          },
        ),
      )
      ..loadRequest(Uri.parse(widget.notebookUrl));
  }

  Future<void> _injectVideoThumbnailScript() async {
    // WebViewでビデオサムネイルを確実に表示するためのスクリプト
    const script = '''
      (function() {
        console.log('Starting video thumbnail injection...');
        
        // ビデオ要素を処理する関数
        function processVideo(video) {
          console.log('Processing video:', video.src);
          
          // ビデオの属性を設定
          video.setAttribute('playsinline', '');
          video.setAttribute('webkit-playsinline', '');
          video.muted = true;
          video.autoplay = false;
          video.preload = 'metadata';
          
          // poster属性が既に設定されているか確認
          if (video.poster) {
            console.log('Video already has poster:', video.poster);
            return;
          }
          
          // ビデオのメタデータが読み込まれているか確認
          if (video.readyState >= 1) {
            // サムネイル生成のためにシーク
            video.currentTime = 0.1;
            console.log('Set currentTime for loaded video');
          } else {
            // メタデータ読み込み後の処理
            video.addEventListener('loadedmetadata', function() {
              console.log('Metadata loaded for video');
              video.currentTime = 0.1;
              
              // 追加の待機処理
              setTimeout(function() {
                if (!video.poster) {
                  video.currentTime = 0.5;
                }
              }, 100);
            }, { once: true });
          }
          
          // シーク完了時の処理
          video.addEventListener('seeked', function() {
            console.log('Video seeked to:', video.currentTime);
            video.pause();
          }, { once: true });
        }
        
        // 既存のビデオ要素を処理
        const videos = document.querySelectorAll('video');
        console.log('Found ' + videos.length + ' videos');
        videos.forEach(processVideo);
        
        // 動的に追加されるビデオ要素を監視
        const observer = new MutationObserver(function(mutations) {
          mutations.forEach(function(mutation) {
            mutation.addedNodes.forEach(function(node) {
              if (node.nodeName === 'VIDEO') {
                console.log('New video element detected');
                processVideo(node);
              }
              // 子要素にビデオがある場合も処理
              if (node.querySelectorAll) {
                const nestedVideos = node.querySelectorAll('video');
                nestedVideos.forEach(processVideo);
              }
            });
          });
        });
        
        // body要素の監視を開始
        observer.observe(document.body, {
          childList: true,
          subtree: true
        });
        
        console.log('Video thumbnail injection completed');
      })();
    ''';
    
    try {
      await _controller.runJavaScript(script);
      debugPrint('Video thumbnail script injected successfully');
    } catch (e) {
      debugPrint('Error injecting video thumbnail script: $e');
    }
  }

  Future<void> _shareNotebook() async {
    try {
      final shareText = '''
${widget.title}

ノートブックを見る：
${widget.notebookUrl}
''';
      await Share.share(shareText);
    } catch (e) {
      debugPrint('Error sharing notebook: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('共有に失敗しました'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              _controller.reload();
            },
          ),
        ],
      ),
      body: Stack(
        children: [
          if (_errorMessage != null)
            Center(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(
                      Icons.error_outline,
                      size: 64,
                      color: Colors.red,
                    ),
                    const SizedBox(height: 16),
                    Text(
                      _errorMessage!,
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 16),
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton(
                      onPressed: () {
                        setState(() {
                          _errorMessage = null;
                        });
                        _controller.reload();
                      },
                      child: const Text('再読み込み'),
                    ),
                  ],
                ),
              ),
            )
          else
            WebViewWidget(controller: _controller),
          if (_isLoading)
            const Center(
              child: CircularProgressIndicator(),
            ),
        ],
      ),
      floatingActionButton: widget.childId != null && widget.notebookId != null
          ? FloatingActionButton(
              onPressed: _shareNotebook,
              backgroundColor: Colors.indigo,
              foregroundColor: Colors.white,
              child: const Icon(Icons.share),
            )
          : null,
    );
  }
}
