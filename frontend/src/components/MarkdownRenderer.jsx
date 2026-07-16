import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const MarkdownRenderer = ({ content, className = '' }) => {
  return (
    <div className={`markdown-content ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Headings
          h1: ({ node, ...props }) => <h1 className="text-2xl font-bold mb-4 text-white" {...props} />,
          h2: ({ node, ...props }) => <h2 className="text-xl font-bold mb-3 text-white" {...props} />,
          h3: ({ node, ...props }) => <h3 className="text-lg font-semibold mb-2 text-trading-cyan" {...props} />,
          h4: ({ node, ...props }) => <h4 className="text-base font-semibold mb-2 text-gray-200" {...props} />,

          // Paragraphs
          p: ({ node, ...props }) => <p className="mb-3 text-gray-300 leading-relaxed" {...props} />,

          // Lists
          ul: ({ node, ...props }) => <ul className="list-disc list-inside mb-3 space-y-1 text-gray-300" {...props} />,
          ol: ({ node, ...props }) => <ol className="list-decimal list-inside mb-3 space-y-1 text-gray-300" {...props} />,
          li: ({ node, ...props }) => <li className="ml-2" {...props} />,

          // Emphasis
          strong: ({ node, ...props }) => <strong className="font-bold text-white" {...props} />,
          em: ({ node, ...props }) => <em className="italic text-trading-cyan" {...props} />,

          // Code
          code: ({ node, inline, ...props }) =>
            inline ? (
              <code className="px-1.5 py-0.5 bg-gray-800 text-trading-cyan rounded text-sm font-mono" {...props} />
            ) : (
              <code className="block p-3 bg-gray-900 text-trading-cyan rounded-lg text-sm font-mono overflow-x-auto mb-3" {...props} />
            ),
          pre: ({ node, ...props }) => <pre className="mb-3" {...props} />,

          // Links
          a: ({ node, ...props }) => (
            <a
              className="text-trading-blue hover:text-trading-cyan underline transition-colors"
              target="_blank"
              rel="noopener noreferrer"
              {...props}
            />
          ),

          // Blockquotes
          blockquote: ({ node, ...props }) => (
            <blockquote
              className="border-l-4 border-trading-cyan pl-4 py-2 my-3 bg-trading-cyan/5 italic text-gray-300"
              {...props}
            />
          ),

          // Horizontal Rule
          hr: ({ node, ...props }) => <hr className="my-4 border-gray-700" {...props} />,

          // Tables
          table: ({ node, ...props }) => (
            <div className="overflow-x-auto mb-4">
              <table className="min-w-full border border-gray-700 rounded-lg" {...props} />
            </div>
          ),
          thead: ({ node, ...props }) => <thead className="bg-gray-800" {...props} />,
          tbody: ({ node, ...props }) => <tbody className="divide-y divide-gray-700" {...props} />,
          tr: ({ node, ...props }) => <tr className="hover:bg-gray-800/50 transition-colors" {...props} />,
          th: ({ node, ...props }) => (
            <th className="px-4 py-2 text-left text-sm font-semibold text-trading-cyan border border-gray-700" {...props} />
          ),
          td: ({ node, ...props }) => (
            <td className="px-4 py-2 text-sm text-gray-300 border border-gray-700" {...props} />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

export default MarkdownRenderer
