"""Voice input via the browser's Web Speech API.

Renders a microphone button that activates speech recognition in the browser.
On recognition, reloads the page with ?voice_text=<transcript> so Streamlit
can read it as a query parameter — same pattern as geolocation.

Supported: Chrome, Edge (Chromium). Firefox and Safari have no support.
"""
import streamlit as st


def render_voice_button(lang: str = "es-ES", button_id: str = "voice-btn") -> None:
    """Renders a microphone button that listens for speech and redirects with
    ?voice_text=<transcript> on success.

    Args:
        lang:      BCP-47 language tag ('es-ES' or 'pt-PT').
        button_id: HTML id for the button (override when multiple on a page).
    """
    st.html(
        f"""
        <script>
        function startVoice_{button_id.replace('-', '_')}() {{
            var btn = document.getElementById('{button_id}');
            var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {{
                alert('Tu navegador no soporta reconocimiento de voz.\\nUsa Chrome o Edge.');
                return;
            }}
            var recognition = new SpeechRecognition();
            recognition.lang = '{lang}';
            recognition.interimResults = false;
            recognition.maxAlternatives = 1;

            btn.textContent = '🔴 Escuchando…';
            btn.disabled = true;
            btn.style.borderColor = '#e53e3e';

            recognition.onresult = function(event) {{
                var transcript = event.results[0][0].transcript;
                var url = new URL(window.parent.location.href);
                url.searchParams.set('voice_text', transcript);
                window.parent.location.href = url.toString();
            }};

            recognition.onerror = function(event) {{
                btn.textContent = '🎤 Voz';
                btn.disabled = false;
                btn.style.borderColor = '#d0d0d0';
                var msgs = {{
                    'not-allowed':  'Permiso de micrófono denegado.',
                    'no-speech':    'No se detectó voz. Intenta de nuevo.',
                    'network':      'Error de red.',
                    'aborted':      'Reconocimiento cancelado.'
                }};
                alert('Error de voz: ' + (msgs[event.error] || event.error));
            }};

            recognition.onend = function() {{
                btn.textContent = '🎤 Voz';
                btn.disabled = false;
                btn.style.borderColor = '#d0d0d0';
            }};

            recognition.start();
        }}
        </script>
        <button id="{button_id}"
                onclick="startVoice_{button_id.replace('-', '_')}()"
                title="Añadir producto por voz"
                style="padding:5px 10px;border:1px solid #d0d0d0;border-radius:4px;
                       cursor:pointer;background:#fafafa;font-size:13px;color:#333;
                       white-space:nowrap">
            🎤 Voz
        </button>
        """
    )


def read_voice_text() -> str:
    """Reads and clears the ?voice_text query parameter.

    Returns the transcribed text, or '' if none is present.
    Call this before rendering the text input that should be pre-filled.
    """
    import streamlit as st
    if "voice_text" not in st.query_params:
        return ""
    text = st.query_params["voice_text"]
    del st.query_params["voice_text"]
    return text.strip()
