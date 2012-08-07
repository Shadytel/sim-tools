BUILD_DIR           = ./build
BUILD_CLASSES_DIR   = $(BUILD_DIR)/classes
BUILD_JAVACARD_DIR  = $(BUILD_DIR)/javacard
JAVACARD_EXPORT_DIR = $(JAVACARD_SDK_DIR)/api21_export_files
CLASSPATH           = $(JAVACARD_SDK_DIR)/lib/api21.jar:$(JAVACARD_SDK_DIR)/lib/sim.jar
JFLAGS              = -target 1.1 -source 1.3 -g -d $(BUILD_CLASSES_DIR) -classpath $(CLASSPATH)
JC                  = javac

.SUFFIXES: .java .class
.java.class:
	mkdir -p $(BUILD_CLASSES_DIR)
	mkdir -p $(BUILD_JAVACARD_DIR)

	$(JC) $(JFLAGS) $*.java

	$(JAVACARD_SDK_DIR)/bin/converter            \
		-d $(BUILD_JAVACARD_DIR)             \
		-classdir $(BUILD_CLASSES_DIR)       \
	  	-exportpath $(JAVACARD_EXPORT_DIR)   \
		-applet $(APPLET_AID) $(APPLET_NAME) \
		$(PACKAGE_NAME) $(PACKAGE_AID) $(PACKAGE_VERSION)

default: classes

classes: $(SOURCES:.java=.class)

clean:
	$(RM) -rf $(BUILD_DIR)

install:
	$(eval CAP_FILE     := $(shell find $(BUILD_JAVACARD_DIR) -name *.cap))
	$(eval MODULE_AID   := $(shell echo $(APPLET_AID) | sed 's/0x//g' | sed 's/\://g'))
	$(eval INSTANCE_AID := $(shell echo $(APPLET_AID) | sed 's/0x//g' | sed 's/\://g'))
	../sim-tools/bin/shadysim                  \
		$(SHADYSIM_OPTIONS)                \
		-l $(CAP_FILE)                     \
		-i $(CAP_FILE)                     \
		--enable-sim-toolkit               \
		--module-aid $(MODULE_AID)         \
		--instance-aid $(INSTANCE_AID)     \
		--nonvolatile-memory-required 0100 \
		--volatile-memory-for-install 0100 \
		--max-menu-entry-text 10           \
		--max-menu-entries 01
