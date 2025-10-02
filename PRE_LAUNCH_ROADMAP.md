# Discord Bot v2.0 - Pre-Launch Roadmap

**Last Updated:** September 2025
**Target Launch:** TBD
**Current Status:** Core functionality complete, utility commands needed

## 🎯 Overview

This document outlines the remaining functionality required before the Discord Bot v2.0 can be launched to replace the current bot. All core league management features are complete - this roadmap focuses on utility commands, integrations, and user experience enhancements.

## ✅ Completed Core Features

- **Player Information** (`/player`) - Comprehensive player cards with stats
- **Team Management** (`/team`, `/teams`, `/roster`) - Team information and roster breakdown
- **League Operations** (`/league`, `/standings`, `/schedule`) - League-wide information
- **Transaction Management** (`/mymoves`, `/legal`) - Player transaction tracking
- **Voice Channels** (`/voice-channel`) - Automatic gameplay channel creation with cleanup
- **Admin Commands** - League administration and management tools
- **Background Services** - Automated cleanup, monitoring, and maintenance

## 🚧 Remaining Pre-Launch Requirements

### 🔧 Critical Fixes Required

#### 1. Custom Command Backend Support **[HIGH PRIORITY]**
- **Status**: Currently failing
- **Issue**: Custom commands system is not functioning properly
- **Impact**: Users cannot create/manage custom text commands
- **Files**: `commands/custom_commands/`, `services/custom_command_service.py`
- **Dependencies**: Database integration, permissions system
- **Estimated Effort**: 2-3 hours (debugging + fixes)

### 🎮 Utility Commands

#### 2. Weather Command
- **Command**: `/weather [location]`
- **Description**: Display current weather conditions and forecast
- **Features**:
  - Current conditions (temp, humidity, conditions)
  - 3-day forecast
  - Location autocomplete/search
  - Weather icons in embeds
- **API Integration**: OpenWeatherMap or similar service
- **Estimated Effort**: 3-4 hours

#### 3. Charts Display System
- **Command**: `/charts <chart-name>`
- **Description**: Display league charts and infographics by URL
- **Features**:
  - Predefined chart library (standings, stats, schedules)
  - URL-based image display in embeds
  - Chart category organization
  - Admin management of chart URLs
- **Data Storage**: JSON config file or database entries
- **Estimated Effort**: 2-3 hours

#### 4. League Resources Links
- **Command**: `/links <resource-name>`
- **Description**: Quick access to league resources and external links
- **Features**:
  - Categorized resource library (rules, schedules, tools)
  - URL validation and testing
  - Admin management interface
  - Search/autocomplete for resource names
- **Data Storage**: JSON config file or database entries
- **Estimated Effort**: 2-3 hours

### 🖼️ User Profile Management

#### 5. Image Management Commands
- **Commands**:
  - `/set-headshot <url>` - Set player headshot image
  - `/set-fancy-card <url>` - Set player fancy card image
- **Description**: Allow users to customize their player profile images
- **Features**:
  - Image URL validation
  - Size/format checking
  - Preview in response embed
  - Integration with existing player card system
- **Permissions**: User can only modify their own player images
- **Database**: Update player image URLs in database
- **Estimated Effort**: 2-3 hours

### 🎯 Gaming & Entertainment

#### 6. Meme Commands
- **Primary Command**: `/lastsoak`
- **Description**: Classic SBA meme commands for community engagement
- **Features**:
  - `/lastsoak` - Display last player to be "soaked" (statistical reference)
  - Embed formatting with player info and stats
  - Historical tracking of events
- **Data Source**: Database queries for recent player performance
- **Estimated Effort**: 1-2 hours

#### 7. Scouting System
- **Command**: `/scout [options]`
- **Description**: Weighted dice rolling system for scouting mechanics
- **Features**:
  - Multiple dice configurations
  - Weighted probability systems
  - Result interpretation and display
  - Historical scouting logs
- **Complexity**: Custom probability algorithms
- **Estimated Effort**: 3-4 hours

#### 8. Trading System
- **Command**: `/trade [parameters]`
- **Description**: Interactive trading interface and management
- **Features**:
  - Trade proposal system
  - Multi-party trade support
  - Trade validation (roster limits, salary caps)
  - Trade history and tracking
  - Integration with transaction system
- **Complexity**: High - multi-user interactions, complex validation
- **Database**: Trade proposals, approvals, completions
- **Estimated Effort**: 6-8 hours

## 📋 Implementation Priority

### Phase 1: Critical Fixes (Week 1)
1. **Custom Command Backend** - Fix existing broken functionality

### Phase 2: Core Utilities (Week 1-2)
2. **Weather Command** - Popular utility feature
3. **Charts System** - Essential for league management
4. **Links System** - Administrative convenience

### Phase 3: User Features (Week 2)
5. **Image Management** - User profile customization
6. **Meme Commands** - Community engagement

### Phase 4: Advanced Features (Week 3)
7. **Scout Command** - Complex gaming mechanics
8. **Trade Command** - Most complex system

## 🏗️ Architecture Considerations

### Command Organization
```
commands/
├── utilities/
│   ├── weather.py          # Weather command
│   ├── charts.py           # Charts display system
│   └── links.py            # Resource links system
├── profile/
│   └── images.py           # Image management commands
├── gaming/
│   ├── memes.py            # Meme commands (lastsoak)
│   ├── scout.py            # Scouting dice system
│   └── trading.py          # Trade management system
```

### Service Layer Requirements
- **WeatherService**: API integration for weather data
- **ResourceService**: Chart and link management
- **ProfileService**: User image management
- **ScoutingService**: Dice mechanics and probability
- **TradingService**: Complex trade logic and validation

### Database Schema Updates
- **Custom commands**: Fix existing schema issues
- **Resources**: Chart/link storage tables
- **Player images**: Image URL fields
- **Trades**: Trade proposal and history tables

## 🧪 Testing Requirements

### Test Coverage Goals
- **Unit Tests**: All new services and commands
- **Integration Tests**: Database interactions, API calls
- **End-to-End Tests**: Complete command workflows
- **Performance Tests**: Database query optimization

### Test Categories by Feature
- **Weather**: API mocking, error handling, rate limiting
- **Charts/Links**: URL validation, admin permissions
- **Images**: URL validation, permission checks
- **Trading**: Complex multi-user scenarios, validation logic

## 📚 Documentation Updates

### User-Facing Documentation
- Command reference updates
- Feature guides for complex commands (trading, scouting)
- Admin guides for resource management

### Developer Documentation
- Service architecture documentation
- Database schema updates
- API integration guides

## ⚡ Performance Considerations

### Database Optimization
- Index requirements for new tables
- Query optimization for complex operations (trading)
- Cache invalidation strategies

### API Rate Limiting
- Weather API rate limits and caching
- Image URL validation and caching
- Error handling for external services

## 🚀 Launch Checklist

### Pre-Launch Validation
- [ ] All commands functional and tested
- [ ] Database migrations completed
- [ ] API keys and external services configured
- [ ] Error handling and logging verified
- [ ] Performance benchmarks met

### Deployment Requirements
- [ ] Environment variables configured
- [ ] External API credentials secured
- [ ] Database backup procedures tested
- [ ] Rollback plan documented
- [ ] User migration strategy defined

## 📊 Success Metrics

### Functionality Metrics
- **Command Success Rate**: >95% successful command executions
- **Response Time**: <2 seconds average response time
- **Error Rate**: <5% error rate across all commands

### User Engagement
- **Command Usage**: Track usage patterns for new commands
- **User Adoption**: Monitor migration from old bot to new bot
- **Community Feedback**: Collect feedback on new features

## 🔮 Post-Launch Enhancements

### Future Considerations (Not Pre-Launch Blockers)
- Advanced trading features (trade deadline management)
- Enhanced scouting analytics and reporting
- Weather integration with game scheduling
- Mobile-optimized command interfaces
- Advanced user profile customization

---

## 📞 Development Notes

### Current Bot Architecture Strengths
- **Robust Service Layer**: Clean separation of concerns
- **Comprehensive Testing**: 44+ tests with good coverage
- **Modern Discord.py**: Latest slash command implementation
- **Error Handling**: Comprehensive error handling and logging
- **Documentation**: Thorough README files and architectural docs

### Technical Debt Considerations
- **Custom Commands**: Address existing backend issues
- **Database Performance**: Monitor query performance with new features
- **External Dependencies**: Manage API dependencies and rate limits
- **Cache Management**: Implement caching for expensive operations

### Resource Requirements
- **Development Time**: Estimated 20-25 hours total
- **API Costs**: Weather API subscription required
- **Database Storage**: Minimal increase for new features
- **Hosting Resources**: Current infrastructure sufficient

---

**Target Timeline: 2-3 weeks for complete pre-launch readiness**
**Next Steps: Begin with Custom Command backend fixes, then proceed with utility commands**