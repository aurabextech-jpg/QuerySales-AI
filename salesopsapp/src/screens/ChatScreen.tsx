import React, { useState, useRef, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import Markdown from 'react-native-markdown-display';
import Animated, {
  FadeInUp,
  FadeInDown,
  Layout,
} from 'react-native-reanimated';
import HapticFeedback from 'react-native-haptic-feedback';
import { useAppSelector } from '../store/hooks';
import { useTheme } from '../hooks/useTheme';
import { Send, Bot, MoreHorizontal, Mic } from '../constants/icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { QuickActionChip } from '../components/QuickActionChip';
import { WorkflowTimeline } from '../components/WorkflowTimeline';
import type { WorkflowStep } from '../components/WorkflowTimeline';
import { agentApi } from '../services/agentApi';
import type { StreamEvent } from '../services/agentApi';

type Message = {
  id: string;
  role: 'user' | 'agent' | 'system';
  content: string;
  showWorkflow?: boolean;
  isStreaming?: boolean;
  activeAgent?: string;
  activeTool?: string;
};

const hapticOptions = {
  enableVibrateFallback: true,
  ignoreAndroidSystemSettings: false,
};

const QUICK_ACTIONS = [
  'Find new leads',
  'Check my pipeline',
  'Create follow-ups',
];

export const ChatScreen = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'agent',
      content:
        "Hi! I'm your SalesOps Agent.\nI can discover leads, check your CRM, create tasks, and keep your pipeline moving.\n\nWhat would you like to do today?",
    },
  ]);
  const [inputText, setInputText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [showChips, setShowChips] = useState(true);
  const flatListRef = useRef<FlatList>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const { colors, spacing, borderRadius, mode } = useTheme();
  const user = useAppSelector(s => s.auth.user);
  const initials = user?.name
    ? user.name
        .split(' ')
        .map(s => s[0])
        .join('')
        .substring(0, 2)
        .toUpperCase()
    : '';

  const triggerHaptic = (
    type: 'impactLight' | 'notificationSuccess' | 'notificationError',
  ) => {
    HapticFeedback.trigger(type, hapticOptions);
  };

  const updateLastAgentMessage = useCallback(
    (updater: (prev: Message) => Partial<Message>) => {
      setMessages(prev => {
        const copy = [...prev];
        for (let i = copy.length - 1; i >= 0; i--) {
          if (copy[i].role === 'agent') {
            copy[i] = { ...copy[i], ...updater(copy[i]) };
            break;
          }
        }
        return copy;
      });
    },
    [],
  );

  const handleStreamEvent = useCallback(
    (event: StreamEvent) => {
      switch (event.type) {
        case 'run_id':
          break;

        case 'agent':
          updateLastAgentMessage(() => ({
            activeAgent: event.data,
            activeTool: undefined,
          }));
          break;

        case 'tool':
          updateLastAgentMessage(() => ({
            activeTool: event.data,
          }));
          break;

        case 'token':
          updateLastAgentMessage(prev => ({
            content: prev.content + event.data,
          }));
          break;

        case 'done':
          triggerHaptic('notificationSuccess');
          updateLastAgentMessage(() => ({
            isStreaming: false,
            activeAgent: undefined,
            activeTool: undefined,
            showWorkflow: true,
          }));
          setIsTyping(false);
          break;

        case 'error':
          triggerHaptic('notificationError');
          updateLastAgentMessage(prev => ({
            content: prev.content || `⚠️ ${event.data}`,
            isStreaming: false,
            activeAgent: undefined,
            activeTool: undefined,
          }));
          setIsTyping(false);
          break;
      }
    },
    [updateLastAgentMessage],
  );

  const sendMessage = async (text?: string) => {
    const msg = (text || inputText).trim();
    if (!msg || isTyping) {
      return;
    }

    abortRef.current?.();

    triggerHaptic('impactLight');
    setShowChips(false);

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: msg,
    };

    const agentPlaceholder: Message = {
      id: (Date.now() + 1).toString(),
      role: 'agent',
      content: '',
      isStreaming: true,
    };

    setMessages(prev => [...prev, userMsg, agentPlaceholder]);
    setInputText('');
    setIsTyping(true);

    const backendMessages = [...messages, userMsg]
      .filter(m => m.role !== 'system')
      .map(m => ({ role: m.role, content: m.content }));

    const abort = agentApi.chatStream(backendMessages, handleStreamEvent);
    abortRef.current = abort;
  };

  const renderMessage = ({ item }: { item: Message }) => {
    const isUser = item.role === 'user';
    return (
      <Animated.View
        entering={
          isUser
            ? FadeInDown.springify().damping(12).stiffness(100)
            : FadeInUp.springify().damping(12).stiffness(100)
        }
        layout={Layout.springify().damping(14).stiffness(100)}
        style={[
          st.msgWrap,
          {
            alignSelf: isUser ? 'flex-end' : 'flex-start',
            flexDirection: isUser ? 'row-reverse' : 'row',
          },
        ]}
      >
        <View
          style={[
            st.avatar,
            {
              backgroundColor: isUser
                ? colors.primary
                : mode === 'dark'
                ? colors.surfaceHighlight
                : colors.surfaceHighlight,
              borderColor: colors.border,
            },
          ]}
        >
          {isUser ? (
            <Text style={{ color: '#FFF', fontSize: 11, fontWeight: '700' }}>
              {initials}
            </Text>
          ) : (
            <Bot size={14} color={colors.primary} />
          )}
        </View>
        <View
          style={[
            st.bubble,
            { borderRadius: borderRadius.lg },
            isUser
              ? { backgroundColor: colors.primary, borderTopRightRadius: 4 }
              : {
                  backgroundColor:
                    mode === 'dark' ? colors.surface : colors.surfaceHighlight,
                  borderColor: colors.border,
                  borderWidth: 1,
                  borderTopLeftRadius: 4,
                },
          ]}
        >
          {!isUser && item.isStreaming && item.activeAgent && (
            <Animated.View
              entering={FadeInUp.duration(200)}
              style={[st.streamBadge, { backgroundColor: colors.primaryMuted }]}
            >
              <ActivityIndicator
                size="small"
                color={colors.primary}
                style={{ marginRight: 6 }}
              />
              <Text style={[st.streamBadgeText, { color: colors.primary }]}>
                🤖 {item.activeAgent} is thinking…
              </Text>
            </Animated.View>
          )}
          {!isUser && item.isStreaming && item.activeTool && (
            <Animated.View
              entering={FadeInUp.duration(200)}
              style={[st.streamBadge, { backgroundColor: colors.accentMuted }]}
            >
              <Text style={[st.streamBadgeText, { color: colors.accent }]}>
                ⚙️ Calling tool: {item.activeTool}…
              </Text>
            </Animated.View>
          )}

          {item.content ? (
            isUser ? (
              <Text style={[st.msgText, { color: '#FFF' }]}>
                {item.content}
              </Text>
            ) : (
              <Markdown
                style={{
                  body: { color: colors.text, fontSize: 15, lineHeight: 22 },
                  strong: { fontWeight: '700' },
                  em: { fontStyle: 'italic' },
                  bullet_list: { marginLeft: 4 },
                  ordered_list: { marginLeft: 4 },
                  list_item: { marginTop: 2, marginBottom: 2 },
                  link: { color: colors.primary },
                  code_inline: {
                    backgroundColor:
                      mode === 'dark' ? colors.surfaceHighlight : '#e8e8e8',
                    borderRadius: 4,
                    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
                    fontSize: 13,
                  },
                  fence: {
                    backgroundColor:
                      mode === 'dark' ? colors.surfaceHighlight : '#e8e8e8',
                    borderRadius: 6,
                    padding: 10,
                    marginTop: 6,
                    marginBottom: 6,
                    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
                    fontSize: 13,
                  },
                  blockquote: {
                    backgroundColor: colors.primaryMuted,
                    borderLeftColor: colors.primary,
                    borderLeftWidth: 3,
                    paddingLeft: 8,
                    marginLeft: 0,
                  },
                }}
              >
                {item.content}
              </Markdown>
            )
          ) : item.isStreaming ? (
            <View
              style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}
            >
              <ActivityIndicator size="small" color={colors.textMuted} />
            </View>
          ) : null}
        </View>
      </Animated.View>
    );
  };

  return (
    <SafeAreaView
      style={[st.root, { backgroundColor: colors.background }]}
      edges={['top']}
    >
      <View
        style={[st.header, { borderColor: colors.border, padding: spacing.md }]}
      >
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <View
            style={[st.headerIcon, { backgroundColor: colors.primaryMuted }]}
          >
            <Bot size={20} color={colors.primary} />
          </View>
          <View>
            <Text style={[st.headerTitle, { color: colors.text }]}>
              SalesOps Agent
            </Text>
            <View
              style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}
            >
              <View
                style={[st.onlineDot, { backgroundColor: colors.success }]}
              />
              <Text style={[st.headerSub, { color: colors.success }]}>
                Online
              </Text>
              <Text style={[st.headerSub, { color: colors.textMuted }]}>
                {' '}
                · All systems synced
              </Text>
            </View>
          </View>
        </View>
        <TouchableOpacity>
          <MoreHorizontal size={22} color={colors.textMuted} />
        </TouchableOpacity>
      </View>

      <KeyboardAvoidingView
        style={st.flex}
        behavior={'padding'}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 25}
      >
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={item => item.id}
          renderItem={renderMessage}
          contentContainerStyle={[
            st.listContent,
            { padding: spacing.md, gap: spacing.md },
          ]}
          onContentSizeChange={() =>
            flatListRef.current?.scrollToEnd({ animated: true })
          }
          showsVerticalScrollIndicator={false}
          ListFooterComponent={
            <>
              {showChips && (
                <Animated.View
                  entering={FadeInUp.delay(300)}
                  style={st.chipsRow}
                >
                  {QUICK_ACTIONS.map(a => (
                    <QuickActionChip
                      key={a}
                      label={a}
                      onPress={() => sendMessage(a)}
                    />
                  ))}
                </Animated.View>
              )}
            </>
          }
        />

        {isTyping &&
          !messages.some(
            m => m.isStreaming && (m.activeAgent || m.content),
          ) && (
            <Animated.View
              entering={FadeInDown}
              style={[st.typingRow, { paddingHorizontal: spacing.md }]}
            >
              <ActivityIndicator size="small" color={colors.primary} />
              <Text style={[st.typingText, { color: colors.textMuted }]}>
                Agent is thinking...
              </Text>
            </Animated.View>
          )}

        <View
          style={[
            st.composer,
            {
              backgroundColor: mode === 'dark' ? colors.surface : colors.card,
              borderColor: colors.border,
              padding: spacing.md,
            },
          ]}
        >
          <View
            style={[
              st.inputWrap,
              {
                backgroundColor: colors.background,
                borderColor: colors.border,
                borderRadius: borderRadius.xl,
              },
            ]}
          >
            <TextInput
              style={[st.input, { color: colors.text }]}
              placeholder="Ask me anything..."
              placeholderTextColor={colors.textMuted}
              value={inputText}
              onChangeText={setInputText}
              multiline
              maxLength={1000}
            />
          </View>
          <TouchableOpacity
            style={[
              st.sendBtn,
              {
                backgroundColor: !inputText.trim()
                  ? colors.surfaceHighlight
                  : colors.primary,
              },
            ]}
            onPress={() => sendMessage()}
            disabled={!inputText.trim() || isTyping}
          >
            <Send
              size={18}
              color={!inputText.trim() ? colors.textMuted : '#FFF'}
            />
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const st = StyleSheet.create({
  root: { flex: 1 },
  flex: { flex: 1 },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottomWidth: 1,
  },
  headerIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: { fontSize: 16, fontWeight: '700' },
  headerSub: { fontSize: 12, fontWeight: '500' },
  onlineDot: { width: 6, height: 6, borderRadius: 3 },
  listContent: { paddingBottom: 20 },
  msgWrap: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    maxWidth: '85%',
    marginVertical: 2,
  },
  avatar: {
    width: 28,
    height: 28,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
  },
  bubble: { padding: 12, flexShrink: 1 },
  msgText: { fontSize: 15, lineHeight: 22 },
  // Streaming badges
  streamBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
    marginBottom: 6,
  },
  streamBadgeText: { fontSize: 12, fontWeight: '600' },
  chipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginVertical: 4,
  },
  typingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingBottom: 8,
  },
  typingText: { fontSize: 13, fontStyle: 'italic' },
  composer: {
    flexDirection: 'row',
    borderTopWidth: 1,
    alignItems: 'flex-end',
    gap: 8,
  },
  inputWrap: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    paddingHorizontal: 14,
  },
  input: {
    flex: 1,
    fontSize: 15,
    maxHeight: 100,
    minHeight: 38,
    paddingVertical: 8,
  },
  micBtn: { padding: 4 },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    paddingLeft: 2,
  },
});
