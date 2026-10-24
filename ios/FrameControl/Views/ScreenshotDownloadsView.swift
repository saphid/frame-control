import SwiftUI

struct ScreenshotDownloadsView: View {
    @ObservedObject var downloads: ScreenshotDownloads
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Toggle("Save screenshots to Photos", isOn: Binding(get: { downloads.saveToPhotos }, set: downloads.setPhotos))
                } footer: {
                    Text("Enabled by default. Turn off to keep new downloads only in Frame Control. Existing Photos are kept. App-only downloads stay app-only when this is turned on again.")
                }
                Section {
                    Text(downloads.message)
                    Text("Automatic downloads begin with new screenshots after the first connection. Keep the app open and connected; background delivery is not available yet.")
                        .foregroundStyle(.secondary)
                }
                Section("Downloaded from this headset") {
                    if downloads.items.isEmpty { Text("No new screenshots downloaded yet.").foregroundStyle(.secondary) }
                    ForEach(downloads.items) { item in
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(item.date, format: .dateTime.month().day().hour().minute())
                                Text(item.status).font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            ShareLink(item: item.file) { Image(systemName: "square.and.arrow.up") }
                                .accessibilityLabel("Share screenshot")
                        }
                    }
                }
            }
            .navigationTitle("Screenshot downloads")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
    }
}
